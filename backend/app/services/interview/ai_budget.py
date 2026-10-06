"""Atomic conservative reservations; failures/retries never refund possibly billed calls."""
import os
import time
from fastapi import HTTPException
from app.models.ai_budget import AIBudget


def enabled():
    from app.core.config import get_settings
    raw = os.getenv('PROMPTCODE_AI_KILL_SWITCH')
    return raw.lower() not in {'1','true','yes','on'} if raw is not None else not get_settings().ai_kill_switch


def positive(name, default):
    from app.core.config import get_settings
    configured = getattr(get_settings(), name.removeprefix('PROMPTCODE_').lower(), default)
    try: value=int(os.getenv(name,str(configured)))
    except ValueError: raise HTTPException(503,'Invalid AI budget configuration')
    if value<=0: raise HTTPException(503,'AI budget is disabled')
    return value


def _trial_enabled():
    """Whether an additional lifetime/trial ceiling applies.

    The old hardcoded $5 trial cap is gone. Spending is still bounded by the
    global, per-user and per-session caps below; a deployment may add an extra
    lifetime ceiling with PROMPTCODE_AI_TRIAL_ENABLED=true.
    """
    from app.core.config import get_settings
    raw = os.getenv('PROMPTCODE_AI_TRIAL_ENABLED')
    if raw is not None:
        return raw.strip().lower() in {'1','true','yes','on'}
    # getattr: settings may be a partial object in tests and older deployments.
    return bool(getattr(get_settings(), 'ai_trial_enabled', False))


async def reserve_ai_budget(db, user_id, session_id, input_bytes, output_tokens=2048, attempts=2):
    if not enabled(): raise HTTPException(503,'AI assistant is temporarily disabled')
    if not (0 <= input_bytes <= 256000 and 1 <= output_tokens <= 4096 and 1 <= attempts <= 8):
        raise HTTPException(400,'AI request exceeds budget size')
    # UTF-8 bytes plus framing overhead conservatively bound input token count.
    tokens=(input_bytes+512+output_tokens)*attempts
    cost=tokens*positive('PROMPTCODE_AI_MAX_MICROS_PER_TOKEN',100)
    day=int(time.time())//86400
    scopes=[('global:'+str(day),'GLOBAL',1000,10000000,20000000),
            (f'user:{user_id}:{day}','USER',100,1000000,5000000),
            (f'session:{session_id}','SESSION',20,200000,2000000)]
    if _trial_enabled():
        scopes.insert(0, ('trial:all', 'TRIAL', 1000000, 1000000000, 5000000))
    dialect=db.get_bind().dialect.name
    if dialect=='postgresql': from sqlalchemy.dialects.postgresql import insert
    elif dialect=='sqlite': from sqlalchemy.dialects.sqlite import insert
    else: raise HTTPException(503,'Unsupported AI budget database')
    try:
        for key,scope,requests_cap,tokens_cap,cost_cap in scopes:
            caps=[positive(f'PROMPTCODE_AI_{scope}_REQUESTS',requests_cap),positive(f'PROMPTCODE_AI_{scope}_TOKENS',tokens_cap),positive(f'PROMPTCODE_AI_{scope}_COST_MICROS',cost_cap)]
            if 1>caps[0] or tokens>caps[1] or cost>caps[2]: raise HTTPException(429,'AI budget exhausted')
            stmt=insert(AIBudget).values(key=key,requests=1,tokens=tokens,cost_micros=cost)
            stmt=stmt.on_conflict_do_update(index_elements=[AIBudget.key],set_={
                'requests':AIBudget.requests+1,'tokens':AIBudget.tokens+tokens,'cost_micros':AIBudget.cost_micros+cost},
                where=(AIBudget.requests+1<=caps[0])&(AIBudget.tokens+tokens<=caps[1])&(AIBudget.cost_micros+cost<=caps[2])).returning(AIBudget.key)
            if (await db.execute(stmt)).scalar_one_or_none() is None: raise HTTPException(429,'AI budget exhausted')
        await db.commit()
    except BaseException:
        await db.rollback()
        raise


# Worker calls run in threads; the identity follows asyncio.to_thread and is
# captured by the relay before its HTTP server starts new threads.
from contextlib import contextmanager
from contextvars import ContextVar

_billing_identity = ContextVar("ai_billing_identity", default=None)


@contextmanager
def billing_identity(user_id, session_id):
    token = _billing_identity.set((str(user_id), str(session_id)))
    try:
        yield
    finally:
        _billing_identity.reset(token)


def current_billing_identity():
    return _billing_identity.get()


def reserve_worker_budget(messages, output_tokens, *, identity=None):
    """Fail closed before each paid synchronous upstream call."""
    import asyncio
    import json
    identity = identity or current_billing_identity()
    if not identity or not all(identity):
        raise HTTPException(503, "AI billing identity unavailable")
    input_bytes = len(json.dumps(messages).encode("utf-8"))

    async def reserve():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from sqlalchemy.pool import NullPool
        from app.core.config import get_settings
        from app.db.session import _connect_args
        # A fresh pool avoids moving asyncpg connections across thread event loops.
        engine = create_async_engine(get_settings().database_url,
                                     poolclass=NullPool, connect_args=_connect_args)
        try:
            async with async_sessionmaker(engine)() as db:
                await reserve_ai_budget(db, *identity, input_bytes,
                                        output_tokens=output_tokens, attempts=1)
        finally:
            await engine.dispose()
    asyncio.run(reserve())
