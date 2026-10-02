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
    observations['interfaces']=[name for _,name in socket.if_nameindex()]
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
