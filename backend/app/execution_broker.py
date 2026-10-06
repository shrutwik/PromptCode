"""Private execution-host broker. No database, provider or grading credentials.

The management listener belongs on a private authenticated TLS network. Only
registered commands and bounded source bytes cross this boundary.
"""
from __future__ import annotations

import asyncio
import hmac
import logging
import os
import re
import tempfile
import time
import uuid
from contextlib import asynccontextmanager, suppress
from pathlib import Path
from typing import Literal

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from app.core.capacity_queue import CapacityExceeded, CapacityQueue, CapacityTimeout
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.services.interview.execution_transfer import SourceBundle, MAX_REQUEST_BYTES
from app.services.interview.registry import get_challenge, get_runner_config
from app.services.interview.runner import IsolatedRunner, resolve_command_id, reap_expired_runners
from app.services.interview.trusted_evaluator import _run_probe
from app.services.interview.trusted_cases import cases_for, VERSION

logger = logging.getLogger(__name__)


def _settings():
    settings = get_settings()
    if not settings.execution_broker_mode:
        raise RuntimeError("Execution broker requires its credential-free service role")
    return settings


def _image(slug):
    cfg = get_runner_config(slug)
    settings = _settings()
    image = settings.broker_python_image if 'python' in cfg['image'] else settings.broker_node_image
    if not image or (not settings.debug and not re.fullmatch(r"[^\s]+@sha256:[a-f0-9]{64}", image)):
        raise HTTPException(503, "Execution image must be configured and pinned by digest")
    return image


class BrokerBoundary:
    """Authenticate and bound bytes/inflight requests before JSON parsing."""
    def __init__(self, app):
        self.app = app
        self.active = 0

    async def __call__(self, scope, receive, send):
        if scope['type'] != 'http':
            return await self.app(scope, receive, send)
        headers = dict(scope['headers'])
        settings = _settings()
        if not hmac.compare_digest(headers.get(b'authorization', b''), ('Bearer ' + settings.sandbox_executor_token).encode()):
            return await self.reject(send, 401)
        if self.active >= settings.max_runners + 4:
            return await self.reject(send, 503)
        self.active += 1
        try:
            body = bytearray()
            while True:
                message = await receive()
                if message['type'] == 'http.disconnect':
                    return
                body.extend(message.get('body', b''))
                if len(body) > MAX_REQUEST_BYTES:
                    return await self.reject(send, 413)
                if not message.get('more_body', False):
                    break
            async def bounded_receive():
                nonlocal body
                data, body = bytes(body), bytearray()
                return {'type': 'http.request', 'body': data, 'more_body': False}
            await self.app(scope, bounded_receive, send)
        finally:
            self.active -= 1

    @staticmethod
    async def reject(send, code):
        await send({'type': 'http.response.start', 'status': code, 'headers': [(b'content-type', b'application/json')]})
        await send({'type': 'http.response.body', 'body': b'{"detail":"Execution broker request rejected"}'})


def reap_broker_resources():
    """Only remove our expired containers and aged transfer directories."""
    import docker
    import shutil
    reap_expired_runners()
    client = docker.from_env(timeout=5)
    try:
        containers = client.containers.list(all=True, filters={"label": [
            "promptcode.role=sandbox", "promptcode.component=execution-broker", "promptcode.expires_at"]})
        for container in containers:
            try:
                expiry = float(container.labels.get("promptcode.expires_at", ""))
                if 0 < expiry <= time.time():
                    container.remove(force=True, v=True)
            except (TypeError, ValueError):
                continue
    finally:
        client.close()
    root = Path(_settings().interview_workspace_root)
    if root.is_dir():
        # Fixed max execution is shorter than one hour. Private root is never
        # mounted in a candidate; candidate containers see only an individual source.
        for path in root.iterdir():
            if (path.name.startswith(("broker-", "pc_")) and path.is_dir()
                    and not path.is_symlink() and path.stat().st_mtime < time.time() - 3600):
                shutil.rmtree(path)


@asynccontextmanager
async def lifespan(app):
    _settings()
    configure_logging()
    async def cleanup():
        while True:
            with suppress(Exception):
                await asyncio.to_thread(reap_broker_resources)
            reap_legacy_jobs()
            await asyncio.sleep(30)
    task = asyncio.create_task(cleanup())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title='PromptCode execution broker', lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
app.add_middleware(BrokerBoundary)

# Bounded, fair admission replaces instant rejection. A saturated execution host
# now makes callers wait in FIFO order up to a bounded backlog and deadline; past
# that the broker still fails closed with 503 + Retry-After. Built lazily because
# the broker role is validated when the service starts, not when it is imported.
_execution_queue: CapacityQueue | None = None


def _queue() -> CapacityQueue:
    global _execution_queue
    if _execution_queue is None:
        settings = _settings()
        _execution_queue = CapacityQueue(
            slots=settings.max_runners,
            max_waiters=settings.max_runner_waiters,
            deadline_seconds=settings.max_runners_acquire_timeout_seconds,
        )
    return _execution_queue


async def execute(operation):
    queue = _queue()
    started = time.monotonic()
    outcome = "failed"
    try:
        await queue.acquire()
        outcome = "admitted"
    except CapacityExceeded as exc:
        outcome = "full"
        raise HTTPException(503, 'Execution capacity reached',
                            headers={'Retry-After': '2'}) from exc
    except CapacityTimeout as exc:
        outcome = "timeout"
        raise HTTPException(503, 'Timed out waiting for execution capacity',
                            headers={'Retry-After': '5'}) from exc
    except asyncio.CancelledError:
        outcome = "cancelled"
        raise
    finally:
        stats = queue.stats()
        logger.info("execution.admission", extra={
            "outcome": outcome, "wait_ms": round((time.monotonic() - started) * 1000, 3),
            "active": stats.active, "waiting": stats.waiting,
            "capacity": stats.slots, "max_waiters": stats.max_waiters,
        })
    slot_released = False

    def release_once() -> None:
        nonlocal slot_released
        if not slot_released:
            slot_released = True
            queue.release()

    task = asyncio.create_task(asyncio.to_thread(operation))
    def finished(task):
        # Retrieve exceptions even after client cancellation, and keep the slot
        # until the worker thread actually stops.
        if not task.cancelled():
            task.exception()
        release_once()
    task.add_done_callback(finished)
    return await asyncio.shield(task)


class InterviewRequest(BaseModel):
    model_config = {'extra': 'forbid'}
    challenge_slug: str = Field(min_length=1, max_length=100)
    source: SourceBundle


class AdvisoryRequest(InterviewRequest):
    command_id: Literal['run_tests', 'run_targeted_tests', 'run_benchmark'] = 'run_tests'


class ProbeRequest(InterviewRequest):
    evaluator_version: str


def require_storage():
    root = Path(_settings().interview_workspace_root)
    root.mkdir(parents=True, exist_ok=True)
    import shutil
    # Reserve all admitted runs' maximum incoming payload, including legacy
    # support files; concurrent requests cannot consume the emergency reserve.
    reserve = getattr(_settings(), 'interview_storage_min_free_bytes', 2 * 1024**3)
    if shutil.disk_usage(root).free < reserve + MAX_REQUEST_BYTES * _settings().max_runners:
        raise HTTPException(503, 'Execution storage capacity reached')
    return root


def _temporary_source(source):
    return tempfile.TemporaryDirectory(prefix='broker-', dir=require_storage())


@app.get('/ready')
async def ready():
    import docker
    def inspect():
        client = docker.from_env(timeout=5)
        try:
            client.ping()
            for slug in ('order-hold-reason', 'invoice-status-transition'):
                client.images.get(_image(slug))
        finally:
            client.close()
    try:
        await asyncio.to_thread(inspect)
    except Exception:
        raise HTTPException(503, 'Execution host not ready') from None
    stats = _queue().stats()
    return {'status': 'ok', 'active': stats.active, 'capacity': _settings().max_runners,
            'waiting': stats.waiting}


@app.post('/v1/interview/run')
async def run(payload: AdvisoryRequest):
    challenge = get_challenge(payload.challenge_slug)
    if challenge is None:
        raise HTTPException(400, 'Unknown challenge')
    cfg = get_runner_config(payload.challenge_slug)
    cfg.update(image=_image(payload.challenge_slug), challengeSlug=payload.challenge_slug)
    command = resolve_command_id(payload.command_id, challenge['test_command'], cfg['commands'])
    def operation():
        with _temporary_source(payload.source) as tmp:
            source = payload.source.materialize(Path(tmp))
            return IsolatedRunner()._run_docker_sync(source, command, cfg['timeoutSeconds'], payload.command_id, cfg)
    return await execute(operation)


def _run_probe_sweep(source, challenge_slug: str, image) -> list[dict]:
    """Run the inventory's independent probes with a bounded worker pool.

    Every case is an independent, read-only probe over the same frozen source, so
    running them concurrently shortens how long one job occupies an execution slot
    (the dominant grading-queue latency). The pool size is bounded by
    ``PROMPTCODE_PROBE_CONCURRENCY`` so a multi-case sweep cannot oversubscribe the
    execution host. Results are returned in inventory order, which is what the
    trusted evaluator cross-checks against.
    """
    inventory = list(cases_for(challenge_slug))
    if not inventory:
        return []
    # Read the plain setting: this helper runs inside an already-admitted
    # operation, so the broker-role check would be redundant here.
    workers = min(max(1, int(get_settings().probe_concurrency)), len(inventory))
    if workers == 1:
        return [{'id': case.id, **_probe_observation(source, challenge_slug, case.probe, image)}
                for case in inventory]
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='probe') as pool:
        futures = [pool.submit(_probe_observation, source, challenge_slug, case.probe, image)
                   for case in inventory]
        results = [future.result() for future in futures]
    return [{'id': case.id, **observation} for case, observation in zip(inventory, results)]


def _probe_observation(source, challenge_slug: str, probe: str, image) -> dict:
    observed, error = _run_probe(source, challenge_slug, probe, image=image)
    return {'observed': observed, 'error': error}


@app.post('/v1/interview/probes')
async def probes(payload: ProbeRequest):
    if get_challenge(payload.challenge_slug) is None or payload.evaluator_version != VERSION:
        raise HTTPException(409, 'Challenge evaluation version changed')
    image = _image(payload.challenge_slug)
    def operation():
        from app.services.runner_capacity import execution_slot
        with execution_slot(), _temporary_source(payload.source) as tmp:
            source = payload.source.materialize(Path(tmp))
            return {'digest': payload.source.digest,
                    'observations': _run_probe_sweep(source, payload.challenge_slug, image)}
    return await execute(operation)

# Legacy candidates call a short-lived local relay. The app worker performs the
# provider call, retaining both provider credentials and shared billing checks.
import threading
from app.services.sandbox.relay import SandboxLLMRelay, RelayError


class LegacyRequest(BaseModel):
    model_config = {'extra': 'forbid'}
    code: str = Field(min_length=1, max_length=120_000)
    entrypoint: str = Field(min_length=1, max_length=120)
    challenge_config: dict
    run_id: str | None = Field(default=None, max_length=100)
    input_overrides: dict | None = None


class LegacyReply(BaseModel):
    model_config = {'extra': 'forbid'}
    id: uuid.UUID
    result: dict | None = None
    error: dict | None = None


def job_error_status(error):
    return error.get('status_code') if isinstance(error, dict) else None


class LegacyJob:
    def __init__(self):
        self.lock = threading.Lock()
        self.event = threading.Event()
        self.call = None
        self.reply = None
        self.last_reply_id = None
        self.result = None
        self.cancelled = False
        self.expires = time.monotonic() + _settings().sandbox_timeout_seconds + 30

    def forward(self, payload):
        with self.lock:
            if self.cancelled or time.monotonic() >= self.expires:
                raise RelayError(503, 'Execution expired')
            if self.call is not None:
                raise RelayError(429, 'Relay call already in progress')
            self.event.clear()
            self.reply = None
            self.call = {'id': str(uuid.uuid4()), 'payload': payload}
        if not self.event.wait(max(0, min(60, self.expires - time.monotonic()))):
            with self.lock:
                self.cancelled = True
                self.call = None
            raise RelayError(504, 'Application relay timed out')
        with self.lock:
            reply = self.reply
            self.call = None
        if self.cancelled or reply is None:
            raise RelayError(503, 'Execution cancelled')
        if reply.error is not None:
            raise RelayError(429 if job_error_status(reply.error) == 429 else 502, 'Application relay rejected request')
        if not isinstance(reply.result, dict):
            raise RelayError(502, 'Invalid application relay response')
        return reply.result

    def cancel(self):
        with self.lock:
            self.cancelled = True
            self.event.set()


_legacy_jobs: dict[str, LegacyJob] = {}


def reap_legacy_jobs():
    for job_id, job in list(_legacy_jobs.items()):
        if time.monotonic() >= job.expires:
            job.cancel()
            del _legacy_jobs[job_id]


def _legacy_job(job_id: uuid.UUID):
    job = _legacy_jobs.get(str(job_id))
    if job is None:
        raise HTTPException(404, 'Execution job not found')
    return job


@app.post('/v1/legacy/jobs')
async def start_legacy(payload: LegacyRequest):
    from app.services.sandbox.runner import _run_in_sandbox_local, _is_safe_entrypoint
    if not _is_safe_entrypoint(payload.entrypoint):
        raise HTTPException(400, 'Invalid entrypoint')
    settings = _settings()
    if not settings.debug and not re.fullmatch(r'[^\s]+@sha256:[a-f0-9]{64}', settings.sandbox_image):
        raise HTTPException(503, 'Sandbox image must be pinned by digest')
    reap_legacy_jobs()
    if _queue().stats().active >= settings.max_runners or len(_legacy_jobs) >= settings.max_runners:
        raise HTTPException(503, 'Execution capacity reached')
    require_storage()
    job_id = str(uuid.uuid4())
    job = LegacyJob()
    _legacy_jobs[job_id] = job
    class ApplicationRelay(SandboxLLMRelay):
        def handle_request(self, payload):
            return job.forward(payload)
    def operation():
        result = _run_in_sandbox_local(payload.code, payload.entrypoint, payload.challenge_config,
            run_id=uuid.uuid4().hex, input_overrides=payload.input_overrides, relay_factory=ApplicationRelay)
        with job.lock:
            job.result = result.to_dict()
    async def background():
        try:
            await execute(operation)
        except Exception:
            with job.lock:
                job.result = {'success': False, 'output': '', 'exit_code': -1, 'telemetry': [], 'error': 'Execution unavailable'}
    task = asyncio.create_task(background())
    # A strong reference keeps the background task alive through client polling.
    job.task = task
    return {'id': job_id}


@app.get('/v1/legacy/jobs/{job_id}')
async def poll_legacy(job_id: uuid.UUID):
    job = _legacy_job(job_id)
    with job.lock:
        if job.result is not None:
            result = job.result
            del _legacy_jobs[str(job_id)]
            return {'status': 'complete', 'result': result}
        return {'status': 'running', 'call': job.call}


@app.post('/v1/legacy/jobs/{job_id}/reply')
async def reply_legacy(job_id: uuid.UUID, payload: LegacyReply):
    job = _legacy_job(job_id)
    with job.lock:
        if job.last_reply_id == str(payload.id):
            return {'ok': True}
        if job.call is None or job.call['id'] != str(payload.id) or job.cancelled:
            raise HTTPException(409, 'Relay call is not current')
        job.reply = payload
        job.last_reply_id = str(payload.id)
        job.event.set()
    return {'ok': True}


@app.delete('/v1/legacy/jobs/{job_id}')
async def cancel_legacy(job_id: uuid.UUID):
    # Wakes blocked relay calls; the fixed Docker execution timeout also bounds
    # CPU-only candidates. Keep the capacity slot until the process is removed.
    _legacy_job(job_id).cancel()
    return {'ok': True}
