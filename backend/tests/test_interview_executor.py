import asyncio
import uuid
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import httpx
import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from app import sandbox_executor as executor
from app.services.interview.runner import IsolatedRunner


def test_api_delegates_only_session_and_command(monkeypatch, tmp_path):
    import json

    from app.core import config
    sid = uuid.uuid4()
    monkeypatch.setattr(config, 'get_settings', lambda: SimpleNamespace(sandbox_executor_url='http://executor:8090', sandbox_executor_token='internal-token'))
    def respond(request):
        assert str(request.url) == 'http://executor:8090/v1/interview/run'
        assert request.headers['Authorization'] == 'Bearer internal-token'
        assert json.loads(request.content) == {'session_id': str(sid), 'command_id': 'run_tests'}
        return httpx.Response(200, json={'ok': False, 'exit_code': 1, 'stdout': 'test failed', 'stderr': '', 'command': 'pytest -q'})
    original = httpx.AsyncClient
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    result = asyncio.run(IsolatedRunner().run_tests(tmp_path / str(sid), 'pytest -q', runner_config={'image': 'ignored-client-image'}))
    assert result['exit_code'] == 1


def test_executor_rejects_caller_paths_images_and_commands():
    for extra in ['workspace', 'image', 'command', 'runner_config']:
        with pytest.raises(ValidationError):
            executor.InterviewRunRequest(session_id=uuid.uuid4(), **{extra: '/host/root'})
    with pytest.raises(ValidationError):
        executor.InterviewRunRequest(session_id=uuid.uuid4(), command_id='shell')


def test_executor_auth_fails_before_database(monkeypatch):
    monkeypatch.setattr(executor.settings, 'sandbox_executor_token', 'internal-token')
    db = SimpleNamespace(get=AsyncMock())
    with pytest.raises(HTTPException) as exc:
        asyncio.run(executor.run_interview(executor.InterviewRunRequest(session_id=uuid.uuid4()), authorization='Bearer wrong', db=db))
    assert exc.value.status_code == 401
    db.get.assert_not_called()


def test_executor_resolves_trusted_workspace_and_registry(monkeypatch, tmp_path):
    from app.services.interview import workspace
    monkeypatch.setattr(executor.settings, 'sandbox_executor_token', 'internal-token')
    monkeypatch.setattr(workspace, 'workspace_root', lambda: tmp_path)
    sid = uuid.uuid4()
    owned = tmp_path / str(sid)
    owned.mkdir()
    session = SimpleNamespace(workspace_path=str(owned), status='active', expires_at=None, challenge_slug='order-hold-reason')
    db = SimpleNamespace(get=AsyncMock(return_value=session))
    def run(self, root, command, timeout, command_id, cfg):
        assert root == owned
        assert command == 'pytest -q'
        assert cfg['image'] == 'promptcode-runner-python:latest'
        return {'ok': False, 'exit_code': 1, 'stdout': 'assertion failed', 'stderr': '', 'command': command}
    monkeypatch.setattr(IsolatedRunner, '_run_docker_sync', run)
    result = asyncio.run(executor.run_interview(executor.InterviewRunRequest(session_id=sid), authorization='Bearer internal-token', db=db))
    assert result['exit_code'] == 1
    session.workspace_path = '/etc'
    with pytest.raises(HTTPException) as exc:
        asyncio.run(executor.run_interview(executor.InterviewRunRequest(session_id=sid), authorization='Bearer internal-token', db=db))
    assert exc.value.status_code == 400


@pytest.mark.skipif(__import__('os').getenv('PROMPTCODE_AUDIT_DOCKER') != '1', reason='Live Docker execution opt-in required')
@pytest.mark.parametrize('slug', [item['slug'] for item in __import__('json').loads((Path(__file__).resolve().parents[2] / 'challenges/interview-registry.json').read_text())['challenges']])
def test_live_executor_runs_registered_question(slug, monkeypatch, tmp_path):
    from app.services.interview import workspace
    monkeypatch.setattr(executor.settings, 'sandbox_executor_token', 'internal-token')
    monkeypatch.setattr(workspace, 'workspace_root', lambda: tmp_path)
    sid = uuid.uuid4()
    owned = workspace.create_workspace(str(sid), slug)
    session = SimpleNamespace(workspace_path=str(owned), status='active', expires_at=None, challenge_slug=slug)
    db = SimpleNamespace(get=AsyncMock(return_value=session))
    result = asyncio.run(executor.run_interview(executor.InterviewRunRequest(session_id=sid), authorization='Bearer internal-token', db=db))
    # Execution is advisory; a green process without a trusted inventory is
    # deliberately not promoted to an authoritative correctness result.
    assert result.get('error_code') in (None, 'incomplete_test_report'), result
    assert result['authoritative'] is False
    assert not result['timed_out'], result
    assert result['counts']['total'] > 0, __import__('json').dumps(result)
    assert result['runner'] == 'docker'


def test_executor_reaps_expired_runners_on_startup(monkeypatch):
    from app.services.interview import runner
    calls = []
    monkeypatch.setattr(runner, 'reap_expired_runners', lambda: calls.append('reaped'))
    async def check():
        async with executor.lifespan(executor.app):
            assert calls == ['reaped']
    asyncio.run(check())
