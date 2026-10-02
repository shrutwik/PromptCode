"""Bounded local Docker attacks. Explicit opt-in; all fixtures contain test data."""
import asyncio
import json
import os
import uuid

import pytest

from app.services.interview.runner import IsolatedRunner

pytestmark = pytest.mark.skipif(os.getenv("PROMPTCODE_AUDIT_DOCKER") != "1", reason="Live local Docker audit requires explicit PROMPTCODE_AUDIT_DOCKER=1")


def test_live_candidate_has_loopback_but_no_peer_network(tmp_path):
    import docker
    client = docker.from_env(timeout=10)
    name = "pc-audit-" + uuid.uuid4().hex[:10]
    network = client.networks.create(name, internal=True, labels={"promptcode.audit": "test-only"})
    victim = None
    try:
        victim = client.containers.run(
            "promptcode-runner-python:latest", ["python", "-m", "http.server", "8765", "--bind", "0.0.0.0"],
            name=name, network=network.name, detach=True, read_only=True, cap_drop=["ALL"],
            security_opt=["no-new-privileges"], mem_limit="64m", pids_limit=16,
            labels={"promptcode.audit": "test-only"},
        )
        victim.reload()
        address = victim.attrs["NetworkSettings"]["Networks"][network.name]["IPAddress"]
        workspace = tmp_path / "candidate"
        workspace.mkdir(mode=0o777)
        workspace.chmod(0o777)
        source = '''import json,socket
from pathlib import Path

def test_network():
    observations={}
    for name,host,port in [('peer',ADDRESS,8765),('internet','1.1.1.1',443),('metadata','169.254.169.254',80),('host','host.docker.internal',8765)]:
        try:
            with socket.create_connection((host,port),timeout=1): observations[name]=True
        except OSError: observations[name]=False
    with socket.socket() as server:
        server.bind(('127.0.0.1',0))
        server.listen(1)
        with socket.create_connection(server.getsockname(),timeout=1):
            connection,_=server.accept()
            connection.close()
            observations['loopback']=True
    observations['interfaces']=[name for _,name in socket.if_nameindex() if int(Path('/sys/class/net',name,'flags').read_text(),16)&1]
    Path('probe.json').write_text(json.dumps(observations))
    assert observations['loopback']
    assert observations['interfaces']==['lo']
    assert not any(observations[name] for name in ('peer','internet','metadata','host')),observations
'''.replace("ADDRESS", repr(address))
        (workspace / "test_network.py").write_text(source)
        result = asyncio.run(IsolatedRunner().run_tests(workspace, "pytest -q", runner_config={"image": "promptcode-runner-python:latest", "timeoutSeconds": 15, "memoryMb": 128, "cpuLimit": .5, "pidsLimit": 32}))
        assert result["ok"], result
        observations = json.loads((workspace / "probe.json").read_text())
        assert observations["loopback"]
        assert observations["interfaces"] == ["lo"]
        assert not observations["peer"]
    finally:
        if victim is not None:
            victim.remove(force=True)
        network.remove()
        client.close()


def test_live_candidate_cannot_read_host_secrets_or_write_root(tmp_path, monkeypatch):
    workspace = tmp_path / "candidate"
    workspace.mkdir(mode=0o777)
    workspace.chmod(0o777)
    sentinel = tmp_path / "host-only-test-secret"
    sentinel.write_text("test-data-never-production")
    monkeypatch.setenv("PROMPTCODE_AUDIT_TEST_SECRET", "test-data-never-production")
    source = '''import os
from pathlib import Path

def test_host_boundary():
    assert os.getuid()!=0
    assert not Path('/var/run/docker.sock').exists()
    assert not Path(HOST_PATH).exists()
    assert not any(name.startswith('PROMPTCODE_') for name in os.environ)
    assert 'OPENAI_API_KEY' not in os.environ
    status=Path('/proc/self/status').read_text()
    caps=next(line.split(':',1)[1].strip() for line in status.splitlines() if line.startswith('CapEff:'))
    assert int(caps,16)==0
    privilege=next(line.split(':',1)[1].strip() for line in status.splitlines() if line.startswith('NoNewPrivs:'))
    assert privilege=='1'
    try:
        Path('/etc/pc-audit-marker').write_text('test-only')
    except OSError:
        pass
    else:
        raise AssertionError('Root filesystem writable')
'''.replace("HOST_PATH", repr(str(sentinel)))
    (workspace / "test_host.py").write_text(source)
    result = asyncio.run(IsolatedRunner().run_tests(workspace, "pytest -q", runner_config={"image": "promptcode-runner-python:latest", "timeoutSeconds": 15, "memoryMb": 128, "cpuLimit": .5, "pidsLimit": 32}))
    assert result["ok"], result
    assert sentinel.read_text() == "test-data-never-production"
