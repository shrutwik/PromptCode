#!/usr/bin/env python3
"""Beta smoke against an isolated sqlite DB (honest local check).

For production DB, run alembic upgrade head first, then exercise the live server
with a real browser. Docker E2E is not required for this smoke.
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import uuid
from pathlib import Path

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

os.environ.setdefault("PROMPTCODE_DEBUG", "true")
os.environ.setdefault("PROMPTCODE_JWT_SECRET", "test-only-secret-not-used-in-prod")

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine  # noqa: E402

import app.models  # noqa: F401, E402
from app.core.config import get_settings  # noqa: E402
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import create_app  # noqa: E402

PASSWORD = "Str0ng!P@ssw0rd"


async def main() -> int:
    get_settings.cache_clear()
    with tempfile.TemporaryDirectory() as tmp:
        db_path = Path(tmp) / "smoke.db"
        engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
        factory = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async def override_get_db():
            async with factory() as session:
                yield session

        from app import main as main_module
        from app.db import session as session_module

        session_module.engine = engine
        session_module.async_session_factory = factory
        main_module.engine = engine
        app = create_app()
        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        suffix = uuid.uuid4().hex[:8]
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            print("health", (await client.get("/health")).status_code)
            print("ready", (await client.get("/health/ready")).status_code)

            async def signup(email: str, username: str) -> str:
                r = await client.post(
                    "/api/auth/signup",
                    json={
                        "email": email,
                        "username": username,
                        "password": PASSWORD,
                        "first_name": "Smoke",
                        "last_name": "Test",
                    },
                )
                assert r.status_code == 201, r.text
                return r.json()["access_token"]

            token_a = await signup(f"smoke_a_{suffix}@example.com", f"smoke_a_{suffix}")
            token_b = await signup(f"smoke_b_{suffix}@example.com", f"smoke_b_{suffix}")
            ha = {"Authorization": f"Bearer {token_a}"}
            hb = {"Authorization": f"Bearer {token_b}"}

            challenges = await client.get("/api/interview/challenges")
            assert challenges.status_code == 200
            slug = challenges.json()[0]["slug"]

            start = await client.post(
                "/api/interview/sessions", headers=ha, json={"challenge_slug": slug}
            )
            assert start.status_code == 200, start.text
            sid = start.json()["id"]

            assert (await client.get(f"/api/interview/sessions/{sid}/files", headers=ha)).status_code == 200
            assert (await client.get(f"/api/interview/sessions/{sid}/files", headers=hb)).status_code == 404

            sub = await client.post(f"/api/interview/sessions/{sid}/submit", headers=ha)
            assert sub.status_code == 200, sub.text
            assert (await client.get(f"/api/interview/sessions/{sid}/report", headers=ha)).status_code == 200
            assert (
                await client.post(
                    f"/api/interview/sessions/{sid}/feedback",
                    headers=ha,
                    json={"realism": 4, "difficulty": 3, "text": "smoke"},
                )
            ).status_code == 200

            dash = await client.get("/api/interview/dashboard", headers=ha)
            assert dash.status_code == 200
            assert any(s["id"] == sid for s in dash.json()["sessions"])

            print("SMOKE OK session=", sid, "challenge=", slug)
            print("NOTE: Docker runner E2E not required in this smoke (submit uses configured runner).")

        app.dependency_overrides.clear()
        await engine.dispose()
        get_settings.cache_clear()
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
