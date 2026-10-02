import asyncio
import base64
import hashlib
import hmac
import logging
import re
import time
import uuid
from contextlib import asynccontextmanager
from functools import lru_cache
from pathlib import Path

import httpx
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import (
    FileResponse,
    HTMLResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.routes import auth, challenges, chat, interview, leaderboard, submissions, users
from app.core.config import get_settings
from app.core.body_limit import BodyLimitMiddleware
from app.core.startup_security import invalid_deployment_token, validate_production_startup
from app.core.logging import configure_logging, reset_request_id, set_request_id
from app.core.metrics import (
    get_metrics_registry,
    http_request_duration_seconds,
    http_requests_total,
)
from app.db.session import engine

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
logger = logging.getLogger(__name__)


def resolve_frontend_html(page: str) -> Path | None:
    """Return one HTML file inside the frontend directory."""
    if not page or page in {".", ".."} or "/" in page or "\\" in page or "\x00" in page:
        return None
    root = FRONTEND_DIR.resolve()
    candidate = (root / f"{page}.html").resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    return candidate


access_logger = logging.getLogger("app.access")


def runner_mode_safe() -> str:
    try:
        from app.services.interview.runner import runner_mode

        return runner_mode()
    except Exception:
        return "unknown"
_INLINE_SCRIPT_RE = re.compile(
    r"<script(?P<attrs>[^>]*)>(?P<body>.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)


@lru_cache
def _frontend_inline_script_hashes() -> tuple[str, ...]:
    if not FRONTEND_DIR.exists():
        return ()

    hashes: set[str] = set()
    for html_path in FRONTEND_DIR.glob("*.html"):
        source = html_path.read_text(encoding="utf-8")
        for match in _INLINE_SCRIPT_RE.finditer(source):
            attrs = match.group("attrs") or ""
            if re.search(r"\bsrc\s*=", attrs, re.IGNORECASE):
                continue

            body = match.group("body")
            if not body.strip():
                continue

            digest = hashlib.sha256(body.encode("utf-8")).digest()
            hash_b64 = base64.b64encode(digest).decode("ascii")
            hashes.add(f"'sha256-{hash_b64}'")

    return tuple(sorted(hashes))


def _content_security_policy() -> str:
    script_sources = [
        "'self'",
        "https://esm.sh",
        "https://cdn.jsdelivr.net",
        *_frontend_inline_script_hashes(),
    ]
    return "; ".join(
        [
            "default-src 'self'",
            f"script-src {' '.join(script_sources)}",
            "script-src-attr 'none'",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com https://cdn.jsdelivr.net",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data:",
            "connect-src 'self' https://esm.sh https://cdn.jsdelivr.net",
            "worker-src 'self' blob: https://cdn.jsdelivr.net",
            "object-src 'none'",
            "base-uri 'self'",
            "frame-ancestors 'none'",
            "form-action 'self'",
        ]
    )


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _content_security_policy()
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if not get_settings().debug:
            response.headers["Strict-Transport-Security"] = (
                "max-age=31536000; includeSubDomains"
            )
        return response


class AccessLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        token = set_request_id(rid)
        started_at = time.perf_counter()
        client_ip = request.client.host if request.client else "unknown"
        try:
            try:
                response = await call_next(request)
            except Exception:
                duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
                route = request.scope.get("route")
                path_label = route.path if route else request.url.path
                http_requests_total.labels(
                    method=request.method, path=path_label, status_code="500"
                ).inc()
                http_request_duration_seconds.labels(
                    method=request.method, path=path_label
                ).observe(duration_ms / 1000.0)
                access_logger.info(
                    "request.complete",
                    extra={
                        "method": request.method,
                        "path": request.url.path,
                        "status_code": 500,
                        "duration_ms": duration_ms,
                        "client_ip": client_ip,
                    },
                )
                raise
            route = request.scope.get("route")
            path_label = route.path if route else request.url.path
            duration_ms = round((time.perf_counter() - started_at) * 1000, 2)
            http_requests_total.labels(
                method=request.method,
                path=path_label,
                status_code=str(response.status_code),
            ).inc()
            http_request_duration_seconds.labels(
                method=request.method, path=path_label
            ).observe(duration_ms / 1000.0)
            response.headers["X-Request-ID"] = rid
            access_logger.info(
                "request.complete",
                extra={
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                    "client_ip": client_ip,
                },
            )
            return response
        finally:
            reset_request_id(token)


_READY_DB_TIMEOUT_SECONDS = 5.0


async def _database_ready() -> bool:
    """Ping the database, and give up if it does not answer quickly."""
    try:
        async with asyncio.timeout(_READY_DB_TIMEOUT_SECONDS):
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
    except Exception:
        return False
    return True


async def _sandbox_executor_ready(settings) -> bool:
    executor_url = str(settings.sandbox_executor_url or "").strip()
    if not executor_url:
        return True

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{executor_url.rstrip('/')}/ready")
    except httpx.HTTPError as exc:
        logger.warning("Sandbox executor readiness check failed: %s", exc)
        return False

    return response.status_code == 200


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_production_startup(get_settings())
    reaper_task = None
    if runner_mode_safe() == "docker":
        from app.services.interview.runner import reap_expired_runners

        async def cleanup():
            try:
                await asyncio.to_thread(reap_expired_runners)
            except Exception:
                logger.warning("Expired runner cleanup unavailable")

        async def repeat_cleanup():
            while True:
                await asyncio.sleep(30)
                await cleanup()

        try:
            await asyncio.wait_for(cleanup(), timeout=15)
        except TimeoutError:
            logger.warning("Expired runner cleanup timed out at startup")
        reaper_task = asyncio.create_task(repeat_cleanup())
    try:
        yield
    finally:
        if reaper_task is not None:
            reaper_task.cancel()
            try:
                await reaper_task
            except asyncio.CancelledError:
                pass
        await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.exception("Unhandled application error for %s", request.url.path, exc_info=exc)
        detail = str(exc) if settings.debug else "Internal server error"
        return JSONResponse(
            status_code=500,
            content={"detail": detail},
        )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Session-Token", "X-Request-ID"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(BodyLimitMiddleware)
    app.add_middleware(AccessLogMiddleware)

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(challenges.router, prefix="/api/challenges", tags=["challenges"])
    app.include_router(submissions.router, prefix="/api/submissions", tags=["submissions"])
    app.include_router(leaderboard.router, prefix="/api/leaderboard", tags=["leaderboard"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
    app.include_router(interview.router, prefix="/api/interview", tags=["interview"])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/health/ready")
    async def health_ready():
        if not await _database_ready():
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "database unavailable"},
            )
        try:
            mode = runner_mode_safe()
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "runner config unavailable"},
            )
        if not await _sandbox_executor_ready(settings):
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "sandbox executor unavailable"},
            )
        return {"status": "ok", "runner": mode}

    @app.get("/ready")
    async def ready():
        if not await _database_ready():
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "database unavailable"},
            )
        if not await _sandbox_executor_ready(settings):
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "sandbox executor unavailable"},
            )
        return {"status": "ok"}

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint(request: Request):
        token = get_settings().metrics_token.strip()
        supplied = request.headers.get("Authorization", "").encode("utf-8")
        if invalid_deployment_token(token) or not hmac.compare_digest(
            supplied, f"Bearer {token}".encode("utf-8")
        ):
            return PlainTextResponse("Unauthorized", status_code=401)
        return PlainTextResponse(generate_latest(get_metrics_registry()), media_type=CONTENT_TYPE_LATEST)

    if FRONTEND_DIR.exists():
        @app.get("/", response_class=HTMLResponse)
        async def serve_index():
            return FileResponse(FRONTEND_DIR / "index.html")

        @app.get("/challenges", response_class=HTMLResponse)
        async def serve_interview_challenges():
            return FileResponse(FRONTEND_DIR / "interview-challenges.html")

        @app.get("/challenges/{slug}", response_class=HTMLResponse)
        async def serve_interview_challenge_detail(slug: str):
            return FileResponse(FRONTEND_DIR / "interview-challenge.html")

        @app.get("/session/{session_id}", response_class=HTMLResponse)
        async def serve_interview_session(session_id: str):
            return FileResponse(FRONTEND_DIR / "interview-session.html")

        @app.get("/session/{session_id}/report", response_class=HTMLResponse)
        async def serve_interview_report(session_id: str):
            return FileResponse(FRONTEND_DIR / "interview-report.html")

        @app.get("/dashboard", response_class=HTMLResponse)
        async def serve_interview_dashboard():
            return FileResponse(FRONTEND_DIR / "interview-dashboard.html")

        @app.get("/onboarding.html", response_class=HTMLResponse)
        @app.get("/onboarding", response_class=HTMLResponse)
        async def serve_onboarding():
            return FileResponse(FRONTEND_DIR / "interview-onboarding.html")

        @app.get("/privacy.html", response_class=HTMLResponse)
        @app.get("/privacy", response_class=HTMLResponse)
        async def serve_privacy():
            return FileResponse(FRONTEND_DIR / "interview-privacy.html")

        @app.get("/settings.html", response_class=HTMLResponse)
        @app.get("/settings", response_class=HTMLResponse)
        async def serve_settings():
            return FileResponse(FRONTEND_DIR / "interview-settings.html")

        @app.get("/login", include_in_schema=False)
        async def redirect_login(request: Request):
            query = f"?{request.url.query}" if request.url.query else ""
            return RedirectResponse(url=f"/login.html{query}", status_code=307)

        @app.get("/signup", include_in_schema=False)
        async def redirect_signup(request: Request):
            query = f"?{request.url.query}" if request.url.query else ""
            return RedirectResponse(url=f"/signup.html{query}", status_code=307)

        @app.get("/practice", include_in_schema=False)
        async def redirect_practice():
            return RedirectResponse(url="/dashboard", status_code=307)

        @app.get("/{page}.html", response_class=HTMLResponse)
        async def serve_page(page: str):
            file_path = resolve_frontend_html(page)
            if file_path is not None:
                return FileResponse(file_path)
            return JSONResponse(status_code=404, content={"detail": "Page not found"})

        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    return app


app = create_app()
