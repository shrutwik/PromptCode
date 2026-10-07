"""Modal deployment entry point for the PromptCode backend.

Deploy from the repository root::

    modal deploy backend/modal_app.py

What this app serves
--------------------
``fastapi_app``
    The existing FastAPI application (``app.main:app``) through ``@modal.asgi_app()``.
    The app itself is not modified or re-implemented here.
``grade_pending_jobs``
    The durable interview-grading worker. It runs the existing
    ``app.workers.interview_grading.process_one_grading_job`` claim/lease loop, so the
    Postgres job queue stays the single source of truth and concurrent runs are safe.
    It is scheduled every ``PROMPTCODE_MODAL_GRADING_POLL_SECONDS`` and can also be
    invoked with ``.spawn()`` from the API for low-latency grading. It is a plain
    Modal Function, not a web endpoint, so it is not bound by the 150 s Web Function
    HTTP request timeout
    (https://modal.com/docs/guide/webhook-timeouts).
``supabase_keepalive``
    A ``modal.Cron`` ``SELECT 1`` so a free-plan Supabase project is not paused after
    7 days of database inactivity
    (https://supabase.com/docs/guides/platform/free-project-pausing).

Runtime configuration
---------------------
Every ``PROMPTCODE_*`` value (plus ``DEEPSEEK_API_KEY``/``MODAL_TOKEN_ID``/
``MODAL_TOKEN_SECRET``) is read from the Modal Secret named by
``PROMPTCODE_MODAL_SECRET_NAME``. Secrets therefore never enter this file, the image,
the frontend or a candidate sandbox.

Only the handful of deploy-time knobs below are read at import time, by
``modal deploy`` on the operator's machine. They are intentionally *not* fields of
``app.core.config.Settings`` (that file is frozen for this migration) and must not be
added to ``.env.example``:

``PROMPTCODE_MODAL_APP_NAME``
    Modal App name (matches ``Settings.modal_app_name``); default ``promptcode``.
``PROMPTCODE_MODAL_SECRET_NAME``
    Name of the Modal Secret holding the runtime environment; default ``promptcode-env``.
``PROMPTCODE_MODAL_KEEPALIVE_CRON``
    Crontab for the keep-alive; default ``0 */6 * * *`` (UTC).
``PROMPTCODE_MODAL_GRADING_POLL_SECONDS``
    Grading poll cadence in seconds; default ``60``.
``PROMPTCODE_MODAL_GRADING_MAX_CONTAINERS``
    Cap on concurrent grading containers; default ``2``.

Pinned against ``modal==1.6.1`` (see ``backend/requirements.txt``).
"""
from __future__ import annotations

import asyncio
import os
import time
from pathlib import Path

import modal

REPO_ROOT = Path(__file__).resolve().parent.parent
BACKEND_DIR = REPO_ROOT / "backend"
_BACKEND_REMOTE_DIR = "/root/backend"

_APP_NAME = (os.environ.get("PROMPTCODE_MODAL_APP_NAME") or "promptcode").strip() or "promptcode"
_ENV_SECRET_NAME = (os.environ.get("PROMPTCODE_MODAL_SECRET_NAME") or "promptcode-env").strip()
_KEEPALIVE_CRON = (os.environ.get("PROMPTCODE_MODAL_KEEPALIVE_CRON") or "0 */6 * * *").strip()
_GRADING_POLL_SECONDS = int(os.environ.get("PROMPTCODE_MODAL_GRADING_POLL_SECONDS") or "60")
_GRADING_MAX_CONTAINERS = int(os.environ.get("PROMPTCODE_MODAL_GRADING_MAX_CONTAINERS") or "2")

# Container hard caps. The grading body additionally bounds itself with
# ``Settings.modal_function_timeout_seconds`` so the configured budget, not this
# constant, is what an operator tunes.
_GRADING_FUNCTION_TIMEOUT_SECONDS = 3600
_HTTP_FUNCTION_TIMEOUT_SECONDS = 600

app = modal.App(_APP_NAME)

# The runtime environment. Create it with, for example:
#   modal secret create promptcode-env PROMPTCODE_DATABASE_URL=... PROMPTCODE_JWT_SECRET=...
env_secret = modal.Secret.from_name(_ENV_SECRET_NAME)

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install_from_requirements(str(BACKEND_DIR / "requirements.txt"))
    .env({"PYTHONPATH": _BACKEND_REMOTE_DIR})
    # Public CA certificate used to verify Supabase's database TLS connection.
    .add_local_file(
        str(BACKEND_DIR / "supabase-ca.crt"),
        remote_path=f"{_BACKEND_REMOTE_DIR}/supabase-ca.crt",
    )
    # Only the application package is shipped. The frontend is served by Vercel, and
    # candidate code never runs in this image (it runs in Modal Sandboxes).
    .add_local_dir(str(BACKEND_DIR / "app"), remote_path=f"{_BACKEND_REMOTE_DIR}/app")
    # Runtime data, not source. ``app/services/interview/registry.py`` resolves the
    # challenge registry and every starter tree as ``parents[4]/challenges`` (the
    # repository root), so without this the app cannot start a challenge at all.
    # ``node_modules`` is excluded: the starter copy skips it, it accounts for
    # ~608 MB of the 613 MB tree, and the candidate sandbox image supplies the
    # per-challenge dependency layer instead.
    .add_local_dir(
        str(REPO_ROOT / "challenges"),
        remote_path="/root/challenges",
        ignore=["**/node_modules", "**/__pycache__", "**/.pytest_cache", "**/dist", "**/build"],
    )
    # ``app/services/evaluation/weight_profile.py`` resolves the evaluator weight
    # profile and its integrity lock relative to the backend directory.
    .add_local_dir(
        str(BACKEND_DIR / "benchmarks"),
        remote_path=f"{_BACKEND_REMOTE_DIR}/benchmarks",
        ignore=["**/__pycache__"],
    )
)


async def _drain_grading_queue(*, budget_seconds: float) -> int:
    """Claim and finish durable grading jobs until the queue is empty or time is up.

    ``process_one_grading_job`` claims each job with a Postgres lease and re-queues
    expired leases, so any number of these drain loops may run concurrently without
    publishing a duplicate or stale result. No work is tracked in process memory:
    stopping at any point leaves the remaining jobs queued for the next run.
    """
    from app.core.ratelimit import cleanup_expired_counters
    from app.db.session import async_session_factory, engine
    from app.workers.interview_grading import process_one_grading_job

    deadline = time.monotonic() + max(0.0, budget_seconds)
    processed = 0
    try:
        async with async_session_factory() as db:
            await cleanup_expired_counters(db=db)
            await db.commit()
        while time.monotonic() < deadline:
            if not await process_one_grading_job():
                break
            processed += 1
    finally:
        # Each invocation runs in its own fresh event loop; pooled asyncpg
        # connections must not be reused across loops.
        await engine.dispose()
    return processed


def _run_grading_drain(budget_seconds: int = 0) -> int:
    """Validate the deployment, then drain the queue for one bounded run."""
    from app.core.config import get_settings
    from app.core.startup_security import validate_production_startup

    settings = get_settings()
    validate_production_startup(settings)
    configured = float(settings.modal_function_timeout_seconds)
    budget = min(float(budget_seconds or configured), configured)
    return asyncio.run(_drain_grading_queue(budget_seconds=budget))


@app.function(
    image=image,
    secrets=[env_secret],
    timeout=_HTTP_FUNCTION_TIMEOUT_SECONDS,
    max_containers=4,
    cpu=0.125,
    memory=512,
    # Page data should not wait for a fresh Python process after idle periods.
    min_containers=1,
    scaledown_window=300,
)
@modal.asgi_app()
def fastapi_app():
    """Serve the unmodified FastAPI application (``app.main:app``)."""
    from app.main import app as application

    return application


@app.function(
    image=image,
    secrets=[env_secret],
    timeout=_GRADING_FUNCTION_TIMEOUT_SECONDS,
    max_containers=_GRADING_MAX_CONTAINERS,
    schedule=modal.Period(seconds=_GRADING_POLL_SECONDS),
)
def grade_pending_jobs(budget_seconds: int = 0) -> int:
    """Drain the durable interview-grading queue; returns the number of jobs finished.

    Scheduled every ``PROMPTCODE_MODAL_GRADING_POLL_SECONDS`` and also safe to call
    eagerly from the API so a submitted interview does not wait for the next tick::

        from modal import Function
        Function.from_name("promptcode", "grade_pending_jobs").spawn()

    ``budget_seconds`` defaults to ``PROMPTCODE_MODAL_FUNCTION_TIMEOUT_SECONDS``.
    """
    return _run_grading_drain(budget_seconds)


@app.function(
    image=image,
    secrets=[env_secret],
    timeout=120,
    schedule=modal.Cron(_KEEPALIVE_CRON),
)
def supabase_keepalive() -> str:
    """Touch the database so a free Supabase project is not paused after 7 days idle.

    Gated on ``PROMPTCODE_SUPABASE_KEEPALIVE_ENABLED``: the schedule stays deployed
    but the run is a no-op when the setting is false.
    """
    from sqlalchemy import text

    from app.core.config import get_settings

    settings = get_settings()
    if not settings.supabase_keepalive_enabled:
        return "skipped: PROMPTCODE_SUPABASE_KEEPALIVE_ENABLED is false"

    async def ping() -> None:
        from app.db.session import engine

        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
        finally:
            await engine.dispose()

    asyncio.run(ping())
    return "ok"
