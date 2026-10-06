import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker

from app.models.ai_budget import AIBudget
from app.services.interview import ai_budget


def _database(tmp_path, monkeypatch):
    from app.core import config
    from app.db import session
    url = 'sqlite+aiosqlite:///' + str(tmp_path / 'shared.db')
    monkeypatch.setattr(config, 'get_settings', lambda: SimpleNamespace(database_url=url, ai_kill_switch=False))
    monkeypatch.setattr(session, '_connect_args', {})
    monkeypatch.setenv('PROMPTCODE_AI_MAX_MICROS_PER_TOKEN', '1')
    async def create():
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            await conn.run_sync(AIBudget.__table__.create)
        await engine.dispose()
    asyncio.run(create())
    return url


def test_assistant_and_concurrent_workers_share_global_cap(tmp_path, monkeypatch):
    url = _database(tmp_path, monkeypatch)
    monkeypatch.setenv('PROMPTCODE_AI_GLOBAL_REQUESTS', '2')
    async def assistant():
        engine = create_async_engine(url)
        async with async_sessionmaker(engine)() as db:
            await ai_budget.reserve_ai_budget(db, 'user', 'question', 10, output_tokens=600, attempts=1)
        await engine.dispose()
    asyncio.run(assistant())
    def worker(i):
        with ai_budget.billing_identity('user', f'evaluation:{i}'):
            try:
                ai_budget.reserve_worker_budget([{'role': 'user', 'content': 'Grade this code'}], 600)
                return 1
            except HTTPException as exc:
                assert exc.status_code == 429
                return 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        assert sum(pool.map(worker, range(8))) == 1


def test_trial_budget_survives_daily_reset(tmp_path, monkeypatch):
    _database(tmp_path, monkeypatch)
    # The lifetime/trial ceiling is opt-in now that the hardcoded $5 cap is gone.
    # Enable it here so this test still covers the trial scope it was written against.
    monkeypatch.setenv('PROMPTCODE_AI_TRIAL_ENABLED', 'true')
    monkeypatch.setenv('PROMPTCODE_AI_TRIAL_REQUESTS', '1')
    monkeypatch.setattr(ai_budget.time, 'time', lambda: 86400)
    with ai_budget.billing_identity('user', 'one'):
        ai_budget.reserve_worker_budget([{'role': 'user', 'content': 'Grade'}], 600)
    monkeypatch.setattr(ai_budget.time, 'time', lambda: 172800)
    with ai_budget.billing_identity('other-user', 'two'):
        with pytest.raises(HTTPException) as exc:
            ai_budget.reserve_worker_budget([{'role': 'user', 'content': 'Grade'}], 600)
    assert exc.value.status_code == 429


def test_worker_kill_switch_and_missing_identity_fail_closed(monkeypatch):
    with pytest.raises(HTTPException) as exc:
        ai_budget.reserve_worker_budget([], 600)
    assert exc.value.status_code == 503
    monkeypatch.setenv('PROMPTCODE_AI_KILL_SWITCH', 'true')
    with ai_budget.billing_identity('user', 'submission'):
        with pytest.raises(HTTPException) as exc:
            ai_budget.reserve_worker_budget([], 600)
    assert exc.value.status_code == 503


def test_relay_reserves_before_network_and_preserves_owner(monkeypatch):
    from app.services.sandbox.relay import SandboxLLMRelay, SandboxLLMBudget, RelayError
    import httpx
    calls = []
    def denied(messages, output_tokens, *, identity):
        calls.append(identity)
        raise HTTPException(429, 'AI budget exhausted')
    monkeypatch.setattr(ai_budget, 'reserve_worker_budget', denied)
    monkeypatch.setattr(httpx, 'Client', lambda **kwargs: pytest.fail('Network reached after budget denial'))
    with ai_budget.billing_identity('owner', 'evaluation:one'):
        relay = SandboxLLMRelay(api_key='test-key', base_url='https://api.deepseek.com', host_alias='localhost', budget=SandboxLLMBudget(('deepseek-flash',), 10, 18000, 600, 20000, 1))
    with pytest.raises(RelayError) as exc:
        relay._send_upstream_request({'messages': [], 'max_tokens': 600})
    assert exc.value.status_code == 429
    assert calls == [('owner', 'evaluation:one')]


def test_deepseek_relay_maps_legacy_model_without_fallback_calls():
    from app.services.sandbox.relay import SandboxLLMRelay, SandboxLLMBudget
    calls = []
    def sender(payload):
        calls.append(payload)
        assert payload['model'] == 'deepseek-flash'
        assert payload['thinking'] == {'type': 'disabled'}
        return {'model': 'deepseek-flash', 'choices': [{'message': {'content': 'result'}}], 'usage': {'prompt_tokens': 10, 'completion_tokens': 5}}, 1
    relay = SandboxLLMRelay(api_key='test-key', base_url='https://api.deepseek.com', host_alias='localhost', budget=SandboxLLMBudget(('deepseek-flash',), 10, 18000, 600, 20000, 1), request_sender=sender)
    result = relay.handle_request({'model': 'gpt-4o', 'prompt': 'Extract this value', 'max_tokens': 100})
    assert result['model'] == 'deepseek-flash'
    assert len(calls) == 1


def test_judges_cannot_reach_provider_after_budget_denial(monkeypatch):
    import httpx
    import openai
    from app.services.evaluation.ai_judge import _call_judge
    from app.services.evaluation.prompt_quality import _judge_with_llm
    def denied(*args, **kwargs):
        raise HTTPException(429, 'AI budget exhausted')
    monkeypatch.setattr(ai_budget, 'reserve_worker_budget', denied)
    monkeypatch.setattr(httpx, 'post', lambda *args, **kwargs: pytest.fail('Judge reached provider'))
    fake = SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **kwargs: pytest.fail('Prompt judge reached provider'))))
    monkeypatch.setattr(openai, 'OpenAI', lambda **kwargs: fake)
    with pytest.raises(HTTPException):
        _call_judge('Rules', 'Code')
    with pytest.raises(HTTPException):
        _judge_with_llm([{'user': 'Extract json', 'system': '', 'model': 'deepseek-flash'}], 'Question')


def test_worker_sets_identity_from_owned_submission(monkeypatch):
    import uuid
    from unittest.mock import AsyncMock, MagicMock
    from app.workers import evaluate
    sid, uid = uuid.uuid4(), uuid.uuid4()
    submission = SimpleNamespace(id=sid, user_id=uid, challenge_id=uuid.uuid4(), status='pending', code='code', entrypoint='main.py')
    challenge = SimpleNamespace(config={}, description='Question', slug='question', title='Question', category='test')
    db = MagicMock()
    db.get = AsyncMock(side_effect=[submission, challenge])
    db.commit = AsyncMock()
    async def observe(**kwargs):
        assert ai_budget.current_billing_identity() == (str(uid), 'evaluation:' + str(sid))
        assert kwargs['challenge_config']['_ai_billing_identity'] == [str(uid), 'evaluation:' + str(sid)]
        raise HTTPException(429, 'AI budget exhausted')
    monkeypatch.setattr(evaluate, 'evaluate_submission', observe)
    with pytest.raises(HTTPException):
        asyncio.run(evaluate._evaluate(db, str(sid)))
    assert ai_budget.current_billing_identity() is None
