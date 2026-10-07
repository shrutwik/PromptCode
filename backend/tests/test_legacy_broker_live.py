"""Opt-in disposable Docker proof for legacy broker/SDK/app-side relay integration.

No provider network calls: the application relay's upstream sender is stubbed.
The native test broker and app share a test process; this is not a dual-host audit.
"""
import json
import os
import socket
import threading
import time
from types import SimpleNamespace

import pytest

pytestmark = pytest.mark.skipif(os.getenv('PROMPTCODE_AUDIT_DOCKER') != '1', reason='Live Docker opt-in required')


@pytest.fixture
def live_broker(monkeypatch, tmp_path):
    import docker
    import uvicorn
    from docker.models.containers import ContainerCollection

    from app import execution_broker as broker
    from app.core import config
    from app.services import runner_capacity
    from app.services.sandbox import legacy_broker_client, runner
    from app.services.sandbox.relay import SandboxLLMRelay

    daemon = docker.from_env(timeout=5)
    daemon.images.get('promptcode-sandbox:latest')
    settings = SimpleNamespace(execution_broker_mode=True, max_runners=2, debug=True,
        sandbox_executor_token='test-management-secret-' * 3,
        interview_workspace_root=str(tmp_path), interview_storage_min_free_bytes=0,
        sandbox_timeout_seconds=15, sandbox_image='promptcode-sandbox:latest',
        sandbox_memory_limit='128m', sandbox_cpu_limit=1, openai_api_key='',
        openai_base_url='', openai_model='gpt-4o', sandbox_executor_url='',
        max_runner_waiters=8, max_runners_acquire_timeout_seconds=15)
    monkeypatch.setattr(broker, 'get_settings', lambda: settings)
    monkeypatch.setattr(config, 'get_settings', lambda: settings)
    monkeypatch.setattr(runner_capacity, 'get_settings', lambda: settings)
    monkeypatch.setattr(runner, 'settings', settings)
    monkeypatch.setattr(broker, '_legacy_jobs', {})
    # Admission is a bounded CapacityQueue now; reset it so each test starts with
    # every slot free instead of patching the retired _active counter.
    monkeypatch.setattr(broker, '_execution_queue', None)
    monkeypatch.setenv('PROMPTCODE_SANDBOX_HOST_WORKDIR', str(tmp_path))
    monkeypatch.setenv('PROMPTCODE_SANDBOX_NETWORK_MODE', 'bridge')
    starts = []
    original_run = ContainerCollection.run
    def recorded_run(collection, *args, **kwargs):
        container = original_run(collection, *args, **kwargs)
        container.reload()
        starts.append({'id': container.id, 'kwargs': kwargs, 'host': container.attrs['HostConfig']})
        return container
    monkeypatch.setattr(ContainerCollection, 'run', recorded_run)
    provider_calls = []
    class StubbedAppRelay(SandboxLLMRelay):
        def __init__(self, **kwargs):
            def upstream(payload):
                provider_calls.append(payload)
                return ({'model': 'deepseek-flash', 'choices': [{'message': {'content': 'stubbed answer'}}],
                    'usage': {'prompt_tokens': 10, 'completion_tokens': 5, 'total_tokens': 15}}, 12.5)
            super().__init__(request_sender=upstream, **kwargs)
    monkeypatch.setattr(legacy_broker_client, 'SandboxLLMRelay', StubbedAppRelay)
    listener = socket.socket()
    listener.bind(('127.0.0.1', 0))
    listener.listen(20)
    port = listener.getsockname()[1]
    server = uvicorn.Server(uvicorn.Config(broker.app, log_level='error', lifespan='off'))
    thread = threading.Thread(target=server.run, kwargs={'sockets': [listener]}, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(.01)
    assert server.started
    app_settings = SimpleNamespace(execution_broker_url=f'http://127.0.0.1:{port}',
        sandbox_executor_token=settings.sandbox_executor_token, sandbox_timeout_seconds=15,
        openai_api_key='test-provider-secret-never-on-executor', openai_base_url='https://api.deepseek.com',
        openai_model='deepseek-flash')
    yield SimpleNamespace(settings=settings, app_settings=app_settings, calls=provider_calls,
        starts=starts, root=tmp_path, daemon=daemon, run=legacy_broker_client.run_legacy_broker)
    server.should_exit = True
    thread.join(5)
    listener.close()
    # Report cleanup failures, then remove only containers created by this fixture.
    leftovers = []
    for item in starts:
        try:
            container = daemon.containers.get(item['id'])
        except docker.errors.NotFound:
            continue
        leftovers.append(item['id'])
        container.remove(force=True, v=True)
    daemon.close()
    assert not leftovers, 'Legacy execution leaked containers'
    assert not list(tmp_path.glob('pc_*')), 'Legacy execution leaked host source directories'


@pytest.mark.parametrize('model', ['gpt-4o-mini', 'deepseek-flash'])
def test_live_legacy_sdk_uses_app_provider_and_reports_authoritative_usage(live_broker, model):
    target = live_broker
    code = f'''import json, os
from pathlib import Path
from promptcode import llm
assert not Path('/var/run/docker.sock').exists()
for key in ('OPENAI_API_KEY', 'DEEPSEEK_API_KEY', 'PROMPTCODE_DATABASE_URL', 'PROMPTCODE_GRADING_SIGNING_KEY', 'PROMPTCODE_SANDBOX_EXECUTOR_TOKEN'):
    assert key not in os.environ
answer = llm.call({model!r}, 'test prompt', max_tokens=32)
assert Path('/tmp/promptcode_telemetry/calls.jsonl').is_file()
# Candidate telemetry forgery must never become authoritative accounting.
Path('/tmp/promptcode_telemetry/calls.jsonl').write_text('{{"cost_usd":99999}}')
print(json.dumps({{'answer': answer, 'tmp_bytes': os.statvfs('/tmp').f_blocks * os.statvfs('/tmp').f_frsize}}))
'''
    result = target.run(code, 'main.py', {'constraints': {'allowed_models': ['deepseek-flash']}}, settings=target.app_settings)
    assert result.success, result.to_dict()
    output = json.loads(result.output)
    assert output == {'answer': 'stubbed answer', 'tmp_bytes': 64 * 1024**2}
    assert len(target.calls) == 1
    assert target.calls[0]['model'] == 'deepseek-flash'
    assert len(result.telemetry) == 1
    record = result.telemetry[0]
    assert (record['model'], record['tokens_prompt'], record['tokens_completion'], record['tokens_total']) == ('deepseek-flash', 10, 5, 15)
    assert record['cost_usd'] == .000009 and record['latency_ms'] == 12.5
    host = target.starts[0]['host']
    assert host['ReadonlyRootfs'] is True
    assert 'size=64m' in host['Tmpfs']['/tmp']
    assert all(mount.endswith(':ro') for mount in host['Binds'])
    assert host['LogConfig']['Config']['max-size'] == '1m'
    candidate_env = json.dumps(target.starts[0]['kwargs']['environment'])
    assert target.app_settings.openai_api_key not in candidate_env
    assert target.settings.sandbox_executor_token not in candidate_env
    assert not list(target.root.glob('**/calls.jsonl'))


def test_live_legacy_host_writes_fail_and_temporary_disk_fill_is_bounded(live_broker):
    code = '''import errno, json, os
try:
    open('/escape', 'wb').write(b'no')
    raise AssertionError('Root filesystem writable')
except OSError as error:
    assert error.errno in (errno.EROFS, errno.EACCES)
written = 0
try:
    with open('/tmp/fill', 'wb', buffering=0) as output:
        while True:
            written += output.write(b'x' * 1024 * 1024)
except OSError as error:
    assert error.errno == errno.ENOSPC
print(json.dumps({'written': written}))
'''
    result = live_broker.run(code, 'main.py', {}, settings=live_broker.app_settings)
    assert result.success, result.to_dict()
    assert 60 * 1024**2 <= json.loads(result.output)['written'] <= 64 * 1024**2
    assert result.telemetry == [] and live_broker.calls == []


def test_live_legacy_timeout_kills_candidate_and_removes_host_source(live_broker):
    live_broker.settings.sandbox_timeout_seconds = 1
    started = time.monotonic()
    result = live_broker.run('import time; time.sleep(30)', 'main.py', {}, settings=live_broker.app_settings)
    assert result.success is False
    assert time.monotonic() - started < 10
    assert result.telemetry == [] and live_broker.calls == []
