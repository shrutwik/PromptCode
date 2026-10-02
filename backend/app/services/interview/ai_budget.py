"""Atomic conservative reservations; failures/retries never refund possibly billed calls."""
import os
import time
from fastapi import HTTPException
from app.models.ai_budget import AIBudget


def enabled():
    return os.getenv('PROMPTCODE_AI_KILL_SWITCH','').lower() not in {'1','true','yes','on'}


def positive(name, default):
    try: value=int(os.getenv(name,str(default)))
    except ValueError: raise HTTPException(503,'Invalid AI budget configuration')
    if value<=0: raise HTTPException(503,'AI budget is disabled')
    return value


async def reserve_ai_budget(db, user_id, session_id, input_bytes, output_tokens=2048, attempts=2):
    if not enabled(): raise HTTPException(503,'AI assistant is temporarily disabled')
    if input_bytes>256000 or output_tokens>4096 or attempts>8:
        raise HTTPException(400,'AI request exceeds budget size')
    # UTF-8 bytes plus framing overhead conservatively bound input token count.
    tokens=(input_bytes+512+output_tokens)*attempts
    cost=tokens*positive('PROMPTCODE_AI_MAX_MICROS_PER_TOKEN',100)
    day=int(time.time())//86400
    scopes=[('global:'+str(day),'GLOBAL',1000,10000000,20000000),
            (f'user:{user_id}:{day}','USER',100,1000000,5000000),
            (f'session:{session_id}','SESSION',20,200000,2000000)]
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
