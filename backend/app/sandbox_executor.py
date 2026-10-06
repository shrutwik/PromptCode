from __future__ import annotations

import asyncio
import hmac
import logging
from contextlib import asynccontextmanager, suppress
import tempfile
import uuid
from pathlib import Path
from datetime import datetime, timezone
from threading import Lock
from typing import Any, Literal

import docker
from docker.errors import DockerException, ImageNotFound
from fastapi import FastAPI, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.sandbox.runner import _run_in_sandbox_local, _sandbox_temp_root


class SandboxRunRequest(BaseModel):
    code: str = Field(min_length=1, max_length=120_000)
    entrypoint: str = Field(min_length=1, max_length=120)
    challenge_config: dict
    run_id: str | None = None
    input_overrides: dict | None = None


class _ExecutorState:
    def __init__(self) -> None:
        self._lock = Lock()
        self.active_runs = 0
        self.total_runs = 0
        self.successful_runs = 0
        self.failed_runs = 0
        self.last_run_started_at: str | None = None
        self.last_run_finished_at: str | None = None
        self.last_error: str | None = None

    def mark_run_started(self) -> None:
        with self._lock:
            self.active_runs += 1
            self.total_runs += 1
            self.last_run_started_at = _now_iso()

    def mark_run_finished(self, *, success: bool, error: str | None) -> None:
        with self._lock:
            self.active_runs = max(0, self.active_runs - 1)
            self.last_run_finished_at = _now_iso()
            self.last_error = (error or "")[:1500] or None
            if success:
                self.successful_runs += 1
            else:
                self.failed_runs += 1

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return {
                "active_runs": self.active_runs,
                "total_runs": self.total_runs,
                "successful_runs": self.successful_runs,
                "failed_runs": self.failed_runs,
                "last_run_started_at": self.last_run_started_at,
                "last_run_finished_at": self.last_run_finished_at,
                "last_error": self.last_error,
            }


settings = get_settings()


@asynccontextmanager
async def lifespan(app):
    if settings.environment.lower() == "production":
        raise RuntimeError("Production requires the credential-free dedicated execution broker")
    from app.services.interview.runner import reap_expired_runners
    async def cleanup():
        try:
            await asyncio.wait_for(asyncio.to_thread(reap_expired_runners), timeout=15)
        except Exception:
            logging.getLogger(__name__).warning("Expired runner cleanup unavailable")
    async def repeat_cleanup():
        while True:
            await asyncio.sleep(30)
            await cleanup()
    await cleanup()
    task = asyncio.create_task(repeat_cleanup())
    try:
        yield
    finally:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task


app = FastAPI(title="PromptCode Sandbox Executor", lifespan=lifespan)
executor_state = _ExecutorState()
_run_limiter: asyncio.Semaphore | None = None
_run_limiter_capacity: int | None = None
_run_limiter_lock = Lock()


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sandbox_executor_max_concurrent_runs() -> int:
    configured = int(settings.sandbox_executor_max_concurrent_runs or 0)
    return max(1, configured)


def _sandbox_executor_acquire_timeout_seconds() -> float:
    configured = float(settings.sandbox_executor_acquire_timeout_seconds or 0)
    return max(1.0, configured)


def _executor_run_limiter() -> asyncio.Semaphore:
    global _run_limiter
    global _run_limiter_capacity

    capacity = _sandbox_executor_max_concurrent_runs()
    with _run_limiter_lock:
        if _run_limiter is None or _run_limiter_capacity != capacity:
            _run_limiter = asyncio.Semaphore(capacity)
            _run_limiter_capacity = capacity
        return _run_limiter


def _executor_runtime_report() -> dict[str, Any]:
    checks: dict[str, dict[str, Any]] = {}
    overall_ok = True
    client = None
    expected_token = str(settings.sandbox_executor_token or "").strip()

    if expected_token:
        checks["auth"] = {"ok": True, "detail": "token configured"}
    elif settings.debug:
        checks["auth"] = {"ok": True, "detail": "debug mode allows tokenless sandbox executor"}
    else:
        overall_ok = False
        checks["auth"] = {
            "ok": False,
            "detail": "sandbox executor token is not configured",
        }

    try:
        client = docker.from_env(timeout=10)
        client.ping()
        checks["docker"] = {"ok": True, "detail": "daemon reachable"}
    except DockerException as exc:
        overall_ok = False
        checks["docker"] = {"ok": False, "detail": str(exc)}
    else:
        try:
            client.images.get(settings.sandbox_image)
            checks["sandbox_image"] = {
                "ok": True,
                "detail": f"image '{settings.sandbox_image}' available",
            }
        except ImageNotFound:
            overall_ok = False
            checks["sandbox_image"] = {
                "ok": False,
                "detail": f"image '{settings.sandbox_image}' missing",
            }
        except DockerException as exc:
            overall_ok = False
            checks["sandbox_image"] = {"ok": False, "detail": str(exc)}
    finally:
        if client is not None:
            try:
                client.close()
            except Exception:
                pass

    shared_root = _sandbox_temp_root()
    if shared_root is None:
        checks["shared_workdir"] = {
            "ok": True,
            "detail": "no shared workdir configured",
        }
    else:
        try:
            with tempfile.NamedTemporaryFile(dir=shared_root, prefix="pc_exec_check_", delete=True):
                pass
            checks["shared_workdir"] = {
                "ok": True,
                "detail": f"writable: {shared_root}",
            }
        except OSError as exc:
            overall_ok = False
            checks["shared_workdir"] = {
                "ok": False,
                "detail": f"{shared_root}: {exc}",
            }

    return {
        "status": "ok" if overall_ok else "error",
        "checks": checks,
        "limits": {
            "max_concurrent_runs": _sandbox_executor_max_concurrent_runs(),
            "acquire_timeout_seconds": _sandbox_executor_acquire_timeout_seconds(),
        },
        "stats": executor_state.snapshot(),
    }


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", response_model=None)
async def ready():
    report = await asyncio.to_thread(_executor_runtime_report)
    if report["status"] != "ok":
        return JSONResponse(status_code=503, content=report)
    return report


@app.get("/status")
async def status() -> dict[str, Any]:
    return await asyncio.to_thread(_executor_runtime_report)


@app.post("/v1/sandbox/run")
async def run_sandbox(
    payload: SandboxRunRequest,
    authorization: str | None = Header(None),
) -> dict:
    expected_token = str(settings.sandbox_executor_token or "").strip()
    if not expected_token:
        raise HTTPException(
            status_code=503,
            detail="Sandbox executor token is not configured.",
        )
    elif not hmac.compare_digest(
        authorization or "",
        f"Bearer {expected_token}",
    ):
        raise HTTPException(status_code=401, detail="Invalid sandbox executor token.")

    limiter = _executor_run_limiter()
    try:
        await asyncio.wait_for(
            limiter.acquire(),
            timeout=_sandbox_executor_acquire_timeout_seconds(),
        )
    except TimeoutError:
        raise HTTPException(
            status_code=503,
            detail=(
                "Sandbox executor saturated. "
                f"Max concurrent runs: {_sandbox_executor_max_concurrent_runs()}."
            ),
        ) from None

    executor_state.mark_run_started()
    def execute():
        try:
            result = _run_in_sandbox_local(
                payload.code, payload.entrypoint, payload.challenge_config,
                run_id=payload.run_id, input_overrides=payload.input_overrides,
            )
            executor_state.mark_run_finished(success=bool(result.success), error=result.error)
            return result.to_dict()
        except Exception:
            executor_state.mark_run_finished(success=False, error="Execution unavailable")
            raise
    task = asyncio.create_task(asyncio.to_thread(execute))
    task.add_done_callback(lambda _: limiter.release())
    return await asyncio.shield(task)


class InterviewGradeRequest(BaseModel):
    model_config = {"extra": "forbid"}
    job_id: uuid.UUID
    lease_token: str = Field(pattern=r"^[a-f0-9]{64}$")


@app.post("/v1/interview/grade")
async def grade_interview(payload: InterviewGradeRequest,
                          authorization: str | None = Header(None),
                          db: AsyncSession = Depends(get_db)) -> dict:
    expected = str(settings.sandbox_executor_token or "").strip()
    if not expected or len(settings.grading_signing_key.encode()) < 32:
        raise HTTPException(503, "Trusted grading is not configured")
    if not hmac.compare_digest(authorization or "", "Bearer " + expected):
        raise HTTPException(401, "Invalid sandbox executor token")
    from app.models.interview_grading import InterviewGradingJob
    from app.services.interview.snapshot import verify_snapshot
    from app.services.interview.workspace import workspace_root
    from app.services.interview.trusted_evaluator import evaluate_snapshot
    job = await db.get(InterviewGradingJob, payload.job_id)
    if job is None:
        raise HTTPException(404, "Grading job not found")
    from app.services.interview.registry import get_challenge
    from app.services.interview.calibration import challenge_version_for
    if (get_challenge(job.challenge_slug) is None
            or job.challenge_version != challenge_version_for(job.challenge_slug)):
        raise HTTPException(409, "Challenge evaluation version changed; review requires a new attempt")
    expiry = job.lease_expires_at
    if expiry and expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=timezone.utc)
    if (job.status != "running" or not expiry or expiry <= datetime.now(timezone.utc)
            or not hmac.compare_digest(job.lease_token or "", payload.lease_token)):
        raise HTTPException(409, "Grading job lease is not current")
    snapshot = Path(job.snapshot_path)
    owned = workspace_root().resolve() / ".submitted" / str(job.session_id) / job.source_digest / "source"
    if snapshot.is_symlink() or snapshot.resolve() != owned:
        raise HTTPException(400, "Invalid submitted source")
    try:
        verify_snapshot(snapshot, job.source_digest)
    except (OSError, ValueError):
        raise HTTPException(409, "Submitted source integrity check failed") from None
    limiter = _executor_run_limiter()
    try:
        await asyncio.wait_for(limiter.acquire(), timeout=_sandbox_executor_acquire_timeout_seconds())
    except TimeoutError:
        raise HTTPException(503, "Execution capacity reached") from None
    task = asyncio.create_task(asyncio.to_thread(evaluate_snapshot, snapshot,
        session_id=str(job.session_id), job_id=str(job.id), challenge_slug=job.challenge_slug,
        source_digest=job.source_digest, signing_key=settings.grading_signing_key,
        challenge_version=job.challenge_version, lease_token=payload.lease_token))
    task.add_done_callback(lambda _: limiter.release())
    return await asyncio.shield(task)


class InterviewRunRequest(BaseModel):
    model_config = {"extra": "forbid"}
    session_id: uuid.UUID
    command_id: Literal["run_tests", "run_targeted_tests", "run_benchmark"] = "run_tests"


from app.db.session import get_db
from sqlalchemy.ext.asyncio import AsyncSession


@app.post("/v1/interview/run")
async def run_interview(payload: InterviewRunRequest,
                        authorization: str | None = Header(None),
                        db: AsyncSession = Depends(get_db)) -> dict:
    expected = str(settings.sandbox_executor_token or "").strip()
    if not expected:
        raise HTTPException(503, "Sandbox executor token is not configured.")
    if not hmac.compare_digest(authorization or "", "Bearer " + expected):
        raise HTTPException(401, "Invalid sandbox executor token.")
    from app.models.interview_session import InterviewSession
    from app.services.interview.registry import get_challenge, get_runner_config
    from app.services.interview.workspace import workspace_root
    from app.services.interview.lifecycle import require_mutable
    from app.services.interview.runner import IsolatedRunner, resolve_command_id
    session = await db.get(InterviewSession, payload.session_id)
    if session is None:
        raise HTTPException(404, "Session not found")
    require_mutable(session)
    root = workspace_root().resolve()
    workspace = Path(session.workspace_path).resolve()
    if workspace != (root / str(payload.session_id)).resolve() or not workspace.is_relative_to(root):
        raise HTTPException(400, "Invalid session workspace")
    challenge = get_challenge(session.challenge_slug)
    if challenge is None:
        raise HTTPException(404, "Challenge not found")
    cfg = get_runner_config(session.challenge_slug)
    cfg["challengeSlug"] = session.challenge_slug
    command = resolve_command_id(payload.command_id, challenge_test_command=challenge["test_command"],
                                 commands_map=cfg.get("commands"))
    limiter = _executor_run_limiter()
    try:
        await asyncio.wait_for(limiter.acquire(), timeout=_sandbox_executor_acquire_timeout_seconds())
    except TimeoutError:
        raise HTTPException(503, "Execution capacity reached") from None
    task = asyncio.create_task(asyncio.to_thread(IsolatedRunner()._run_docker_sync,
                              workspace, command, int(cfg["timeoutSeconds"]), payload.command_id, cfg))
    task.add_done_callback(lambda _: limiter.release())
    return await asyncio.shield(task)
