"""Adversarial tests for the private, credential-free execution boundary."""
import asyncio
import base64
import hashlib
import json
import time
import uuid
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from app import execution_broker as broker
from app.services.interview.execution_transfer import (
    SourceBundle,
    SourceFile,
    bundle_source,
)
from app.services.interview.snapshot import manifest_digest


def make_bundle(files=None):
    files = files or {'src/main.py': b'print(1)'}
    return SourceBundle(digest=manifest_digest(sorted([
        {'path': path, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest()}
        for path, data in files.items()], key=lambda item: item['path'])),
        files=[{'path': path, 'data': base64.b64encode(data).decode()} for path, data in files.items()])


@pytest.fixture
def configured(monkeypatch, tmp_path):
    settings = SimpleNamespace(execution_broker_mode=True, max_runners=2, debug=True,
        sandbox_executor_token='x' * 48, broker_python_image='approved-python', broker_node_image='approved-node',
        interview_workspace_root=str(tmp_path), sandbox_timeout_seconds=2, sandbox_image='approved-sandbox',
        max_runner_waiters=8, max_runners_acquire_timeout_seconds=1)
    monkeypatch.setattr(broker, 'get_settings', lambda: settings)
    monkeypatch.setattr(broker, '_execution_queue', None)
    monkeypatch.setattr(broker, '_legacy_jobs', {})
    return settings


def saturated_queue(settings, *, waiting: int = 0):
    """A queue holding every slot, for admission-path tests."""
    from app.core.capacity_queue import CapacityQueue
    queue = CapacityQueue(slots=settings.max_runners, max_waiters=settings.max_runner_waiters,
                          deadline_seconds=settings.max_runners_acquire_timeout_seconds)
    for _ in range(settings.max_runners):
        queue._semaphore._value -= 1
        queue._active += 1
    queue._waiting = waiting
    return queue


def client():
    return TestClient(broker.app, headers={'Authorization': 'Bearer ' + 'x' * 48})


@pytest.mark.parametrize('path', ['.', '../etc/passwd', '/etc/passwd', 'a/../../key', 'a\\b', 'a//b', './a', 'a/./b', '.git/config', 'node_modules/a', 'a\x00b'])
def test_source_rejects_unsafe_paths(path):
    with pytest.raises(ValidationError):
        SourceFile(path=path, data='eA==')


def test_source_digest_duplicate_paths_and_prefix_conflicts():
    data = make_bundle().model_dump()
    data['files'].append(data['files'][0])
    with pytest.raises(ValidationError):
        SourceBundle(**data)
    with pytest.raises(ValidationError):
        make_bundle({'a': b'x', 'a/b': b'y'})
    data = make_bundle().model_dump()
    data['files'][0]['data'] = 'eA=='
    with pytest.raises(ValidationError):
        SourceBundle(**data)


def test_round_trip_has_no_host_paths_and_rejects_links(tmp_path):
    source = tmp_path / 'original'
    source.mkdir()
    (source / 'file.py').write_text('print(1)')
    bundle = bundle_source(source)
    dest = bundle.materialize(tmp_path / 'transfer')
    assert dest.name == 'source'
    assert (dest / 'file.py').read_text() == 'print(1)'
    (source / 'secret.py').symlink_to('/etc/passwd')
    with pytest.raises(ValueError):
        bundle_source(source)


def test_authentication_happens_before_json_or_docker(configured, monkeypatch):
    monkeypatch.setattr(broker, 'execute', lambda *args: pytest.fail('Must not execute'))
    response = TestClient(broker.app).post('/v1/interview/run', content=b'{bad json')
    assert response.status_code == 401


def test_body_bound_before_parsing(configured, monkeypatch):
    monkeypatch.setattr(broker, 'MAX_REQUEST_BYTES', 20)
    assert client().post('/v1/interview/run', content=b'x' * 21).status_code == 413


def test_no_caller_docker_authority(configured):
    payload = {'challenge_slug': 'order-hold-reason', 'source': make_bundle().model_dump()}
    for field in ('image', 'command', 'environment', 'mounts', 'workspace', 'network_mode', 'privileged', 'devices'):
        assert client().post('/v1/interview/run', json={**payload, field: 'attacker'}).status_code == 422
    assert client().post('/v1/interview/run', json={**payload, 'command_id': 'shell'}).status_code == 422


def test_advisory_uses_server_registry_and_disposes_source(configured, monkeypatch):
    paths = []
    def run(self, source, command, timeout, command_id, cfg):
        paths.append(source)
        assert source.is_dir()
        assert str(source).startswith(configured.interview_workspace_root)
        assert cfg['image'] == 'approved-python'
        assert command == 'pytest -q'
        return {'ok': False, 'exit_code': 1, 'stdout': '', 'stderr': '', 'command': command}
    monkeypatch.setattr(broker.IsolatedRunner, '_run_docker_sync', run)
    response = client().post('/v1/interview/run', json={'challenge_slug': 'order-hold-reason', 'source': make_bundle().model_dump()})
    assert response.status_code == 200
    assert not paths[0].exists()


def test_production_requires_pinned_image(configured):
    configured.debug = False
    response = client().post('/v1/interview/run', json={'challenge_slug': 'order-hold-reason', 'source': make_bundle().model_dump()})
    assert response.status_code == 503


def test_saturation_does_not_start_work(configured, monkeypatch):
    monkeypatch.setattr(broker, '_execution_queue', saturated_queue(configured))
    monkeypatch.setattr(broker.IsolatedRunner, '_run_docker_sync', lambda *args: pytest.fail('No capacity'))
    assert client().post('/v1/interview/run', json={'challenge_slug': 'order-hold-reason', 'source': make_bundle().model_dump()}).status_code == 503


def test_cancellation_keeps_execution_slot_until_thread_finishes(configured):
    import threading
    entered, release = threading.Event(), threading.Event()
    def operation():
        entered.set()
        release.wait(2)
    async def exercise():
        queue = broker._queue()
        task = asyncio.create_task(broker.execute(operation))
        await asyncio.to_thread(entered.wait, 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        assert queue.stats().active == 1
        release.set()
        for _ in range(50):
            if queue.stats().active == 0:
                break
            await asyncio.sleep(.01)
        assert queue.stats().active == 0
    asyncio.run(exercise())


def test_full_queue_fails_closed_with_retry_hint(configured, monkeypatch):
    """A bounded backlog refuses the next request instead of queueing forever."""
    monkeypatch.setattr(broker, '_execution_queue',
                        saturated_queue(configured, waiting=configured.max_runner_waiters))
    monkeypatch.setattr(broker.IsolatedRunner, '_run_docker_sync', lambda *args: pytest.fail('No capacity'))
    response = client().post('/v1/interview/run', json={'challenge_slug': 'order-hold-reason', 'source': make_bundle().model_dump()})
    assert response.status_code == 503
    assert response.headers.get('Retry-After')


@pytest.mark.parametrize("outcome", ["admitted", "full", "timeout", "cancelled"])
def test_admission_logs_wait_and_outcome_without_running_refused_work(configured, monkeypatch, caplog, outcome):
    from app.core.capacity_queue import CapacityExceeded, CapacityTimeout, QueueStats

    class Queue:
        async def acquire(self):
            errors = {"full": CapacityExceeded, "timeout": CapacityTimeout,
                      "cancelled": asyncio.CancelledError}
            if outcome in errors:
                raise errors[outcome]()

        def stats(self):
            return QueueStats(slots=2, active=1 if outcome == "admitted" else 2,
                              waiting=0, max_waiters=8)

        def release(self):
            pass

    monkeypatch.setattr(broker, "_queue", Queue)
    ran = []

    async def run():
        if outcome == "admitted":
            assert await broker.execute(lambda: ran.append(True) or "done") == "done"
        else:
            error = asyncio.CancelledError if outcome == "cancelled" else broker.HTTPException
            with pytest.raises(error):
                await broker.execute(lambda: ran.append(True))

    with caplog.at_level("INFO", logger=broker.__name__):
        asyncio.run(run())
    record = next(r for r in caplog.records if r.getMessage() == "execution.admission")
    assert record.outcome == outcome
    assert record.wait_ms >= 0
    assert record.capacity == 2
    assert record.max_waiters == 8
    assert ran == ([True] if outcome == "admitted" else [])


def test_queued_request_waits_for_a_slot_instead_of_shedding(configured):
    """A saturated host admits a queued caller as soon as a slot frees."""
    async def exercise():
        queue = broker._queue()
        holders = [asyncio.create_task(queue.acquire()) for _ in range(configured.max_runners)]
        await asyncio.gather(*holders)
        assert queue.stats().active == configured.max_runners
        waiter = asyncio.create_task(queue.acquire())
        await asyncio.sleep(0.05)
        assert queue.stats().waiting == 1
        assert not waiter.done()
        queue.release()  # one holder finishes and frees a slot
        await waiter
        assert queue.stats().active == configured.max_runners
        assert queue.stats().waiting == 0
        for _ in range(configured.max_runners):
            queue.release()
        assert queue.stats().active == 0
    asyncio.run(exercise())


def test_admission_timing_includes_waiting_for_an_active_slot(configured, caplog):
    async def exercise():
        queue = broker._queue()
        for _ in range(configured.max_runners):
            await queue.acquire()
        task = asyncio.create_task(broker.execute(lambda: "done"))
        try:
            while queue.stats().waiting == 0:
                await asyncio.sleep(0)
            await asyncio.sleep(0.02)
            queue.release()
            assert await task == "done"
        finally:
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
            while queue.stats().active:
                queue.release()

    with caplog.at_level("INFO", logger=broker.__name__):
        asyncio.run(exercise())
    record = next(r for r in caplog.records if r.getMessage() == "execution.admission")
    assert record.outcome == "admitted"
    assert record.wait_ms >= 10


def test_legacy_provider_exchange_is_bounded_idempotent_and_credential_free(configured, monkeypatch):
    from app.services.sandbox import runner
    from app.services.sandbox.relay import SandboxLLMBudget
    def run(code, entrypoint, config, **kwargs):
        relay = kwargs['relay_factory'](api_key='', base_url='', host_alias='localhost',
            budget=SandboxLLMBudget(max_calls=1, max_prompt_chars=100, max_completion_tokens=100, max_total_tokens=200, max_total_cost_usd=1, allowed_models=('model',)))
        result = relay.handle_request({'prompt': 'hi', 'model': 'model'})
        assert result == {'text': 'done'}
        return runner.SandboxResult(success=True, output='done', exit_code=0, telemetry=[])
    monkeypatch.setattr(runner, '_run_in_sandbox_local', run)
    # Context manager preserves the background job's event loop across polls.
    monkeypatch.setattr(broker, 'reap_broker_resources', lambda: 0)
    with client() as transport:
        result = transport.post('/v1/legacy/jobs', json={'code': 'print(1)', 'entrypoint': 'main.py', 'challenge_config': {}})
        assert result.status_code == 200
        job_id = result.json()['id']
        call = None
        for _ in range(100):
            state = transport.get('/v1/legacy/jobs/' + job_id).json()
            call = state.get('call')
            if call:
                break
            time.sleep(.01)
        assert call and call['payload'] == {'prompt': 'hi', 'model': 'model'}
        assert transport.post(f'/v1/legacy/jobs/{job_id}/reply', json={'id': str(uuid.uuid4()), 'result': {}}).status_code == 409
        reply = {'id': call['id'], 'result': {'text': 'done'}}
        assert transport.post(f'/v1/legacy/jobs/{job_id}/reply', json=reply).status_code == 200
        assert transport.post(f'/v1/legacy/jobs/{job_id}/reply', json=reply).status_code == 200
        for _ in range(100):
            state = transport.get('/v1/legacy/jobs/' + job_id).json()
            if state['status'] == 'complete':
                break
            time.sleep(.01)
        assert state['result']['success'] is True
        assert transport.get('/v1/legacy/jobs/' + job_id).status_code == 404


def test_trusted_comparison_and_signing_stay_on_application_host(configured, monkeypatch, tmp_path):
    from app.core import config
    from app.services.interview import trusted_evaluator as evaluator
    configured.execution_broker_url = 'http://broker'
    configured.grading_job_timeout_seconds = 10
    monkeypatch.setattr(config, 'get_settings', lambda: configured)
    bundle = make_bundle()
    source = bundle.materialize(tmp_path / 'app')
    cases = evaluator.cases_for('order-hold-reason')
    secret = 'private-grading-key-' * 4
    def respond(request):
        payload = json.loads(request.content)
        assert secret not in request.content.decode()
        assert set(payload) == {'challenge_slug', 'source', 'evaluator_version'}
        return httpx.Response(200, json={'digest': bundle.digest, 'observations': [
            {'id': case.id, 'observed': case.expected, 'error': None} for case in cases]})
    original = httpx.Client
    monkeypatch.setattr(httpx, 'Client', lambda **kw: original(transport=httpx.MockTransport(respond), **kw))
    identity = dict(session_id=str(uuid.uuid4()), job_id=str(uuid.uuid4()), challenge_slug='order-hold-reason',
        source_digest=bundle.digest, challenge_version='reviewed', lease_token='lease')
    result = evaluator.evaluate_snapshot(source, signing_key=secret, **identity)
    assert evaluator.verify_result(result, signing_key=secret, **identity)['score_percent'] == 100


def test_low_disk_fails_closed_for_legacy_and_interview(configured, monkeypatch):
    import shutil
    monkeypatch.setattr(shutil, 'disk_usage', lambda root: SimpleNamespace(free=0))
    assert client().post('/v1/legacy/jobs', json={'code': 'print(1)', 'entrypoint': 'main.py', 'challenge_config': {}}).status_code == 503
    assert client().post('/v1/interview/run', json={'challenge_slug': 'order-hold-reason', 'source': make_bundle().model_dump()}).status_code == 503
    assert not broker._legacy_jobs


def test_legacy_candidate_cannot_write_execution_host(configured, monkeypatch, tmp_path):
    from app.services.sandbox import runner
    monkeypatch.setattr(runner, 'settings', SimpleNamespace(execution_broker_mode=True,
        sandbox_image='approved', sandbox_memory_limit='512m', sandbox_cpu_limit=1,
        sandbox_timeout_seconds=120))
    relay = SimpleNamespace(proxy_url='http://127.0.0.1:1', token='ephemeral')
    budget = SimpleNamespace(allowed_models=('model',))
    result = runner._build_container_run_kwargs(code_dir=tmp_path/'code', telemetry_dir=tmp_path/'telemetry',
        entrypoint='main.py', relay=relay, budget=budget, network_mode='container:broker', run_id='owned')
    assert result['volumes'] == {str(tmp_path/'code'): {'bind': '/workspace', 'mode': 'ro'}}
    assert result['read_only'] is True
    assert 'size=64m' in result['tmpfs']['/tmp']
    assert result['log_config']['config']['max-size'] == '1m'
    assert result['labels']['promptcode.component'] == 'execution-broker'
    assert 'promptcode.expires_at' in result['labels']
    assert configured.sandbox_executor_token not in json.dumps(result)


def test_grading_worker_retains_snapshot_identity_across_transaction(monkeypatch):
    from contextlib import asynccontextmanager
    from unittest.mock import AsyncMock

    from app.workers import interview_grading as jobs
    job = SimpleNamespace(id=uuid.uuid4(), session_id=uuid.uuid4(), challenge_slug='order-hold-reason',
        challenge_version='reviewed', source_digest='a' * 64, lease_token='lease', attempts=1,
        max_attempts=3, snapshot_path='/owned/submitted/source')
    db = SimpleNamespace(rollback=AsyncMock())
    @asynccontextmanager
    async def session():
        yield db
    async def execute(identity):
        assert identity.snapshot_path == job.snapshot_path
        return {'payload': 'signed'}
    monkeypatch.setattr(jobs, 'async_session_factory', session)
    monkeypatch.setattr(jobs, 'claim_next_job', AsyncMock(return_value=job))
    monkeypatch.setattr(jobs, '_execute', execute)
    finish = AsyncMock()
    monkeypatch.setattr(jobs, 'finish_job', finish)
    monkeypatch.setattr(jobs, 'fail_job', AsyncMock(side_effect=AssertionError('Must not discard snapshot identity')))
    monkeypatch.setattr(jobs, 'get_settings', lambda: SimpleNamespace(grading_job_timeout_seconds=5))
    assert asyncio.run(jobs.process_one_grading_job()) is True
    finish.assert_awaited_once()
