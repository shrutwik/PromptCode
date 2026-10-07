import asyncio
import multiprocessing
import os
import threading

import pytest

from app.core.config import get_settings
from app.services.interview import runner
from app.services.runner_capacity import RunnerBusy, execution_slot


def try_slot(queue):
    try:
        with execution_slot(): queue.put('accepted')
    except RunnerBusy: queue.put('busy')


def test_slots_are_shared_between_processes_and_released(tmp_path, monkeypatch):
    monkeypatch.setenv('PROMPTCODE_INTERVIEW_WORKSPACE_ROOT', str(tmp_path))
    monkeypatch.setenv('PROMPTCODE_MAX_RUNNERS', '1')
    get_settings.cache_clear()
    ctx=multiprocessing.get_context('spawn')
    try:
        with execution_slot():
            queue=ctx.Queue(); process=ctx.Process(target=try_slot,args=(queue,))
            process.start();process.join(10)
            assert process.exitcode==0
            assert queue.get(timeout=1)=='busy'
        with execution_slot(): pass
    finally: get_settings.cache_clear()


def test_cancelled_request_keeps_execution_capacity_until_thread_finishes(tmp_path, monkeypatch):
    started=threading.Event();finish=threading.Event()
    def execute(*args):
        started.set();assert finish.wait(5);return {'ok':False}
    monkeypatch.setattr(runner.IsolatedRunner,'_run_docker_sync',execute)
    async def exercise():
        semaphore=asyncio.Semaphore(1)
        monkeypatch.setattr(runner,'_runner_semaphore',semaphore)
        task=asyncio.create_task(runner.IsolatedRunner().run_tests(tmp_path,'pytest -q'))
        while not started.is_set(): await asyncio.sleep(.01)
        task.cancel()
        with pytest.raises(asyncio.CancelledError): await task
        assert semaphore.locked()
        finish.set()
        for _ in range(100):
            if not semaphore.locked(): break
            await asyncio.sleep(.01)
        assert not semaphore.locked()
    try: asyncio.run(exercise())
    finally: finish.set()


def test_full_waiting_queue_rejects_without_starting_thread(tmp_path, monkeypatch):
    monkeypatch.setattr(runner,'_runner_waiters',get_settings().max_runners*2)
    result=asyncio.run(runner.IsolatedRunner().run_tests(tmp_path,'pytest -q'))
    assert result['error_code']=='runner_busy'


@pytest.mark.skipif(os.getenv('PROMPTCODE_AUDIT_DOCKER')!='1',reason='Live local Docker opt-in required')
def test_live_docker_capacity_has_backpressure_and_cleanup(tmp_path, monkeypatch):
    import docker
    monkeypatch.setenv('PROMPTCODE_INTERVIEW_WORKSPACE_ROOT',str(tmp_path/'slots'))
    monkeypatch.setenv('PROMPTCODE_MAX_RUNNERS','2')
    get_settings.cache_clear()
    workspace=tmp_path/'candidate';workspace.mkdir();workspace.chmod(0o777)
    (workspace/'test_capacity.py').write_text('import time\ndef test_capacity(): time.sleep(2)\n')
    barrier=threading.Barrier(8)
    execute=runner.IsolatedRunner._run_docker_sync
    def synchronized(self,*args):
        barrier.wait(timeout=10)
        return execute(self,*args)
    monkeypatch.setattr(runner.IsolatedRunner,'_run_docker_sync',synchronized)
    async def exercise():
        monkeypatch.setattr(runner,'_runner_semaphore',asyncio.Semaphore(8))
        return await asyncio.gather(*(runner.IsolatedRunner().run_tests(workspace,'pytest -q',runner_config={
            'image':'promptcode-runner-python:latest','expectedTestIds':['test_capacity.py::test_capacity'],
        }) for _ in range(8)))
    try:
        results=asyncio.run(exercise())
        assert sum(r.get('error_code')=='runner_busy' for r in results)==6
        assert sum(r['ok'] for r in results)==2
        client=docker.from_env(timeout=10)
        try:
            leftovers=client.containers.list(all=True,filters={'label':'promptcode.role=interview-runner'})
            assert not [c for c in leftovers if any(m.get('Source')==str(workspace) for m in c.attrs.get('Mounts',[]))]
        finally: client.close()
    finally: get_settings.cache_clear()
