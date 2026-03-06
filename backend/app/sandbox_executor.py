from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from threading import Lock
from typing import Any
import tempfile

import docker
from docker.errors import DockerException, ImageNotFound
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.core.config import get_settings
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
app = FastAPI(title="PromptCode Sandbox Executor")
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

    try:
        client = docker.from_env()
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
    if expected_token:
        if authorization != f"Bearer {expected_token}":
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
    result = None
    try:
        result = await asyncio.to_thread(
            _run_in_sandbox_local,
            payload.code,
            payload.entrypoint,
            payload.challenge_config,
            run_id=payload.run_id,
            input_overrides=payload.input_overrides,
        )
    except Exception as exc:  # pragma: no cover - defensive safety net
        executor_state.mark_run_finished(success=False, error=str(exc))
        limiter.release()
        raise
    try:
        executor_state.mark_run_finished(
            success=bool(result.success),
            error=result.error,
        )
        return result.to_dict()
    finally:
        limiter.release()
