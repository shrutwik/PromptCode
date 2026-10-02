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
        source = '''import atexit,json,socket
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
    atexit.register(lambda: print('NETWORK_PROBE='+json.dumps(observations)))
    assert observations['loopback']
    assert observations['interfaces']==['lo']
    assert not any(observations[name] for name in ('peer','internet','metadata','host')),observations
'''.replace("ADDRESS", repr(address))
        (workspace / "test_network.py").write_text(source)
        result = asyncio.run(IsolatedRunner().run_tests(workspace, "pytest -q", runner_config={"expectedTestIds": ['test_network.py::test_network'], "image": "promptcode-runner-python:latest", "timeoutSeconds": 15, "memoryMb": 128, "cpuLimit": .5, "pidsLimit": 32}))
        assert result["ok"], result
        observations = json.loads(next(line.split("NETWORK_PROBE=", 1)[1] for line in result["stdout"].splitlines() if "NETWORK_PROBE=" in line))
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
    result = asyncio.run(IsolatedRunner().run_tests(workspace, "pytest -q", runner_config={"expectedTestIds": ['test_host.py::test_host_boundary'], "image": "promptcode-runner-python:latest", "timeoutSeconds": 15, "memoryMb": 128, "cpuLimit": .5, "pidsLimit": 32}))
    assert result["ok"], result
    assert sentinel.read_text() == "test-data-never-production"


def test_live_pid_cpu_memory_and_tmp_disk_limits(tmp_path):
    workspace = tmp_path / "candidate"
    workspace.mkdir(mode=0o777)
    workspace.chmod(0o777)
    source = '''import errno,os,signal,time
from pathlib import Path

def test_limits():
    cgroup=Path('/sys/fs/cgroup')
    assert int((cgroup/'memory.max').read_text())==128*1024*1024
    assert int((cgroup/'pids.max').read_text())==32
    quota,period=map(int,(cgroup/'cpu.max').read_text().split())
    assert quota/period==.25
    before=int(dict(line.split() for line in (cgroup/'cpu.stat').read_text().splitlines())['nr_throttled'])
    end=time.process_time()+.4
    while time.process_time()<end: pass
    after=int(dict(line.split() for line in (cgroup/'cpu.stat').read_text().splitlines())['nr_throttled'])
    assert after>before
    children=[]
    blocked=False
    try:
        for _ in range(64):
            try: pid=os.fork()
            except OSError as exc:
                assert exc.errno==errno.EAGAIN
                blocked=True
                break
            if pid==0:
                os.pause()
                os._exit(0)
            children.append(pid)
    finally:
        for pid in children: os.kill(pid,signal.SIGKILL)
        for pid in children: os.waitpid(pid,0)
    assert blocked
    exhausted=False
    path=Path('/tmp/pc-audit-disk')
    try:
        with path.open('wb') as output:
            for _ in range(70): output.write(b'x'*1024*1024)
    except OSError as exc:
        assert exc.errno==errno.ENOSPC
        exhausted=True
    finally:
        path.unlink(missing_ok=True)
    assert exhausted
'''
    (workspace / "test_limits.py").write_text(source)
    result = asyncio.run(IsolatedRunner().run_tests(workspace, "pytest -q", runner_config={"expectedTestIds": ['test_limits.py::test_limits'], "image": "promptcode-runner-python:latest", "timeoutSeconds": 15, "memoryMb": 128, "cpuLimit": .25, "pidsLimit": 32}))
    assert result["ok"], result


def test_live_memory_exhaustion_is_contained(tmp_path):
    workspace = tmp_path / "candidate"
    workspace.mkdir(mode=0o777)
    workspace.chmod(0o777)
    (workspace / "test_memory.py").write_text("def test_memory():\n    payload=bytearray(256*1024*1024)\n    assert payload is not None\n")
    result = asyncio.run(IsolatedRunner().run_tests(workspace, "pytest -q", runner_config={"image": "promptcode-runner-python:latest", "timeoutSeconds": 10, "memoryMb": 64, "cpuLimit": .5, "pidsLimit": 32}))
    assert not result["ok"]
    assert result["exit_code"] == 137, result
    assert not result["timed_out"]


def test_live_huge_output_is_clipped(tmp_path, monkeypatch):
    import docker
    from app.services.interview import runner
    client = docker.from_env(timeout=10)
    collection = client.containers
    create = collection.run
    captured = []
    def capture(*args, **kwargs):
        container = create(*args, **kwargs)
        container.reload()
        captured.append(container.attrs["HostConfig"]["LogConfig"])
        return container
    from types import SimpleNamespace
    monkeypatch.setattr(collection, "run", capture)
    monkeypatch.setattr(runner, "_docker_client", lambda: SimpleNamespace(containers=collection))
    workspace = tmp_path / "candidate"
    workspace.mkdir(mode=0o777)
    workspace.chmod(0o777)
    (workspace / "test_output.py").write_text("def test_output():\n    print('x'*2000000)\n    assert False, 'bounded output probe'\n")
    result = asyncio.run(IsolatedRunner().run_tests(workspace, "pytest -q", runner_config={"image": "promptcode-runner-python:latest", "timeoutSeconds": 15, "memoryMb": 128, "cpuLimit": .5, "pidsLimit": 32, "outputLimit": 1000}))
    assert not result["ok"]
    assert len(result["stdout"]) <= 1000
    assert captured[0]["Type"] == "local"
    assert captured[0]["Config"]["max-size"] == "1m"
    assert captured[0]["Config"]["max-file"] == "1"
    client.close()


def test_live_workspace_fill_is_bounded_and_host_source_is_unchanged(tmp_path):
    workspace = tmp_path / "candidate"
    workspace.mkdir(mode=0o777)
    workspace.chmod(0o777)
    source = """import errno,os
from pathlib import Path

def test_fill():
    stats=os.statvfs('/workspace')
    assert stats.f_blocks*stats.f_frsize==256*1024*1024
    assert 'ro' in next(line.split()[3].split(',') for line in Path('/proc/mounts').read_text().splitlines() if line.split()[1]=='/source')
    blocked=False
    path=Path('/workspace/fill')
    try:
        with path.open('wb') as output:
            for _ in range(270): output.write(b'x'*1024*1024)
    except OSError as exc:
        assert exc.errno==errno.ENOSPC
        blocked=True
    finally:
        path.unlink(missing_ok=True)
    assert blocked
    try: Path('/source/host-marker').write_text('tampered')
    except OSError: pass
    else: raise AssertionError('Host source writable')
"""
    (workspace / "test_fill.py").write_text(source)
    (workspace / "host-marker").write_text("unchanged-test-data")
    before = {p.name: p.read_bytes() for p in workspace.iterdir()}
    result = asyncio.run(IsolatedRunner().run_tests(workspace, "pytest -q", runner_config={"expectedTestIds": ['test_fill.py::test_fill'], "image": "promptcode-runner-python:latest", "timeoutSeconds": 20, "memoryMb": 512, "cpuLimit": .5, "pidsLimit": 32}))
    assert result["ok"], result
    assert {p.name: p.read_bytes() for p in workspace.iterdir()} == before


def test_live_timeout_removes_container_and_volumes(tmp_path, monkeypatch):
    import docker
    from types import SimpleNamespace
    from app.services.interview import runner
    client = docker.from_env(timeout=10)
    collection = client.containers
    create = collection.run
    names = []
    mounts = []
    def capture(**kwargs):
        container = create(**kwargs)
        container.reload()
        names.append(container.name)
        mounts.extend(m["Name"] for m in container.attrs["Mounts"] if m["Type"] == "volume")
        return container
    monkeypatch.setattr(collection, "run", capture)
    monkeypatch.setattr(runner, "_docker_client", lambda: SimpleNamespace(containers=collection))
    workspace = tmp_path / "candidate"
    workspace.mkdir(mode=0o777)
    workspace.chmod(0o777)
    (workspace / "test_hang.py").write_text("import time\ndef test_hang(): time.sleep(60)\n")
    try:
        result = asyncio.run(IsolatedRunner().run_tests(workspace, "pytest -q", runner_config={"image": "promptcode-runner-python:latest", "timeoutSeconds": 1, "memoryMb": 128}))
        assert result["timed_out"], result
        assert len(names) == 1
        assert client.containers.list(all=True, filters={"name": names[0]}) == []
        assert mounts == []  # source bind + tmpfs create no Docker volumes
    finally:
        for name in names:
            try: client.containers.get(name).remove(force=True, v=True)
            except docker.errors.NotFound: pass
        client.close()


def test_live_startup_reaper_after_simulated_crash():
    import docker,time
    from app.services.interview.runner import reap_expired_runners
    client = docker.from_env(timeout=10)
    containers = []
    try:
        for deadline in (time.time()-1, time.time()+120):
            containers.append(client.containers.run(
                "promptcode-runner-python:latest", ["python", "-c", "import time;time.sleep(120)"],
                detach=True, network_disabled=True, read_only=True, mem_limit="64m", pids_limit=16,
                cap_drop=["ALL"], security_opt=["no-new-privileges"],
                labels={"promptcode.role":"interview-runner", "promptcode.component":"interview", "promptcode.expires_at":str(deadline)},
            ))
        assert reap_expired_runners() >= 1
        with pytest.raises(docker.errors.NotFound): client.containers.get(containers[0].id)
        assert client.containers.get(containers[1].id).status == "running"
    finally:
        for container in containers:
            try: container.remove(force=True, v=True)
            except docker.errors.NotFound: pass
        client.close()
