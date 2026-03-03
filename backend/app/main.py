from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.api.routes import challenges, chat, leaderboard, submissions
from app.api.routes import auth, users
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import engine

FRONTEND_DIR = Path(__file__).resolve().parent.parent.parent / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
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
