from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text

from app.api.routes import challenges, chat, leaderboard, submissions
from app.api.routes import auth, users
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Try to ensure tables exist, but don't block startup if the DB
    # (e.g., Supabase) is temporarily unavailable.
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
    except Exception as exc:  # pragma: no cover - best-effort guard
        logger.error("Database initialization failed during startup", exc_info=exc)
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

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
                if not settings.submission_inline_queue_processing:
                    cutoff = datetime.now(timezone.utc) - timedelta(
                        seconds=max(1, settings.worker_heartbeat_timeout_seconds)
                    )
                    worker_result = await conn.execute(
                        text(
                            """
                            SELECT worker_id
                            FROM worker_heartbeats
                            WHERE last_seen_at >= :cutoff
                            LIMIT 1
                            """
                        ),
                        {"cutoff": cutoff},
                    )
                    if worker_result.first() is None:
                        return JSONResponse(
                            status_code=503,
                            content={"status": "error", "detail": "worker unavailable"},
                        )
        except Exception:
            return JSONResponse(
                status_code=503,
                content={"status": "error", "detail": "database unavailable"},
            )
        return {"status": "ok"}

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
