from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.api.routes import submissions as submissions_route
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.challenge import Challenge
from app.models.evaluation_job import EvaluationJob


async def _seed_challenge(session_factory: async_sessionmaker) -> uuid.UUID:
    async with session_factory() as session:
        challenge = Challenge(
            slug="dispatch-check",
            title="Dispatch Check",
            description="Dispatch submission jobs correctly.",
            category="ops",
            config={},
        )
        session.add(challenge)
        await session.commit()
        await session.refresh(challenge)
        return challenge.id


def test_submission_dispatch_runs_inline_when_enabled(monkeypatch):
    db_url = "sqlite+aiosqlite:///:memory:"
    test_engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def create_schema() -> None:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())

    async def override_get_db():
        async with session_factory() as session:
            yield session

    from app import main as main_module
    from app.db import session as session_module

    monkeypatch.setattr(session_module, "engine", test_engine)
    monkeypatch.setattr(session_module, "async_session_factory", session_factory)
    monkeypatch.setattr(main_module, "engine", test_engine)
    monkeypatch.setenv("PROMPTCODE_SUBMISSION_INLINE_QUEUE_PROCESSING", "true")
    get_settings.cache_clear()

    calls: list[str] = []

    async def fake_process_job(job_id: str) -> None:
        calls.append(job_id)

    monkeypatch.setattr(submissions_route, "process_job", fake_process_job)

    challenge_id = asyncio.run(_seed_challenge(session_factory))

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        signup = client.post(
            "/api/auth/signup",
            json={
                "email": "inline@example.com",
                "username": "inline_user",
                "first_name": "Inline",
                "last_name": "User",
                "password": "Password123!",
            },
        )
        assert signup.status_code == 201
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        submission = client.post(
            "/api/submissions/",
            json={
                "challenge_id": str(challenge_id),
                "code": "print('ok')",
                "entrypoint": "main.py",
            },
            headers=headers,
        )
        assert submission.status_code == 201

        async def _job_count() -> int:
            async with session_factory() as session:
                result = await session.execute(select(EvaluationJob))
                return len(list(result.scalars()))

        assert len(calls) == 1
        assert asyncio.run(_job_count()) == 1

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    asyncio.run(test_engine.dispose())


def test_submission_dispatch_skips_inline_when_disabled(monkeypatch):
    db_url = "sqlite+aiosqlite:///:memory:"
    test_engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def create_schema() -> None:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())

    async def override_get_db():
        async with session_factory() as session:
            yield session

    from app import main as main_module
    from app.db import session as session_module

    monkeypatch.setattr(session_module, "engine", test_engine)
    monkeypatch.setattr(session_module, "async_session_factory", session_factory)
    monkeypatch.setattr(main_module, "engine", test_engine)
    monkeypatch.setenv("PROMPTCODE_SUBMISSION_INLINE_QUEUE_PROCESSING", "false")
    get_settings.cache_clear()

    calls: list[str] = []

    async def fake_process_job(job_id: str) -> None:
        calls.append(job_id)

    monkeypatch.setattr(submissions_route, "process_job", fake_process_job)

    challenge_id = asyncio.run(_seed_challenge(session_factory))

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        signup = client.post(
            "/api/auth/signup",
            json={
                "email": "queued@example.com",
                "username": "queued_user",
                "first_name": "Queued",
                "last_name": "User",
                "password": "Password123!",
            },
        )
        assert signup.status_code == 201
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        submission = client.post(
            "/api/submissions/",
            json={
                "challenge_id": str(challenge_id),
                "code": "print('ok')",
                "entrypoint": "main.py",
            },
            headers=headers,
        )
        assert submission.status_code == 201

        async def _fetch_job() -> EvaluationJob | None:
            async with session_factory() as session:
                result = await session.execute(select(EvaluationJob))
                return result.scalar_one_or_none()

        saved_job = asyncio.run(_fetch_job())
        assert saved_job is not None
        assert saved_job.status == "queued"
        assert calls == []

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    asyncio.run(test_engine.dispose())


def test_submission_dispatch_rejects_when_user_exceeds_outstanding_job_limit(monkeypatch):
    db_url = "sqlite+aiosqlite:///:memory:"
    test_engine = create_async_engine(db_url)
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def create_schema() -> None:
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(create_schema())

    async def override_get_db():
        async with session_factory() as session:
            yield session

    from app import main as main_module
    from app.db import session as session_module

    monkeypatch.setattr(session_module, "engine", test_engine)
    monkeypatch.setattr(session_module, "async_session_factory", session_factory)
    monkeypatch.setattr(main_module, "engine", test_engine)
    monkeypatch.setenv("PROMPTCODE_SUBMISSION_INLINE_QUEUE_PROCESSING", "false")
    monkeypatch.setenv("PROMPTCODE_SUBMISSION_MAX_OUTSTANDING_JOBS_PER_USER", "1")
    get_settings.cache_clear()

    challenge_id = asyncio.run(_seed_challenge(session_factory))

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db

    with TestClient(app) as client:
        signup = client.post(
            "/api/auth/signup",
            json={
                "email": "limit@example.com",
                "username": "limit_user",
                "first_name": "Limit",
                "last_name": "User",
                "password": "Password123!",
            },
        )
        assert signup.status_code == 201
        token = signup.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        first_submission = client.post(
            "/api/submissions/",
            json={
                "challenge_id": str(challenge_id),
                "code": "print('ok')",
                "entrypoint": "main.py",
            },
            headers=headers,
        )
        assert first_submission.status_code == 201

        second_submission = client.post(
            "/api/submissions/",
            json={
                "challenge_id": str(challenge_id),
                "code": "print('still ok')",
                "entrypoint": "main.py",
            },
            headers=headers,
        )
        assert second_submission.status_code == 429
        assert "Too many outstanding evaluation jobs" in second_submission.json()["detail"]

        async def _job_count() -> int:
            async with session_factory() as session:
                result = await session.execute(select(EvaluationJob))
                return len(list(result.scalars()))

        assert asyncio.run(_job_count()) == 1

    app.dependency_overrides.clear()
    get_settings.cache_clear()
    asyncio.run(test_engine.dispose())
