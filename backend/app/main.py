from contextlib import asynccontextmanager
from pathlib import Path
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
import httpx
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text

from app.api.routes import challenges, chat, leaderboard, submissions
from app.api.routes import auth, users
from app.core.config import get_settings
from app.core.logging import configure_logging, reset_request_id, set_request_id
from app.core.metrics import (
    get_metrics_registry,
    http_request_duration_seconds,
    http_requests_total,
)
from app.db.session import engine

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
logger = logging.getLogger(__name__)
access_logger = logging.getLogger("app.access")


def _content_security_policy() -> str:
    return "; ".join(
        [
            "default-src 'self'",
            "script-src 'self' 'unsafe-inline' https://esm.sh",
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
            "font-src 'self' https://fonts.gstatic.com",
            "img-src 'self' data:",
            "connect-src 'self'",
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
    yield
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
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(AccessLogMiddleware)

    app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
    app.include_router(users.router, prefix="/api/users", tags=["users"])
    app.include_router(challenges.router, prefix="/api/challenges", tags=["challenges"])
    app.include_router(submissions.router, prefix="/api/submissions", tags=["submissions"])
    app.include_router(leaderboard.router, prefix="/api/leaderboard", tags=["leaderboard"])
    app.include_router(chat.router, prefix="/api/chat", tags=["chat"])

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/ready")
    async def ready():
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
        except Exception:
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
        if token:
            if request.headers.get("Authorization") != f"Bearer {token}":
                return PlainTextResponse("Unauthorized", status_code=401)
        elif not settings.debug:
            return PlainTextResponse("Unauthorized", status_code=401)
        return PlainTextResponse(generate_latest(get_metrics_registry()), media_type=CONTENT_TYPE_LATEST)

    if FRONTEND_DIR.exists():
        @app.get("/", response_class=HTMLResponse)
        async def serve_index():
            return FileResponse(FRONTEND_DIR / "index.html")

        @app.get("/{page}.html", response_class=HTMLResponse)
        async def serve_page(page: str):
            file_path = FRONTEND_DIR / f"{page}.html"
            if file_path.exists():
                return FileResponse(file_path)
            return FileResponse(FRONTEND_DIR / "index.html")

        app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

    return app


app = create_app()
