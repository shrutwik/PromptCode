"""Integration tests for submissions and leaderboard routes."""
from __future__ import annotations

import asyncio
import uuid

import app.models  # noqa: F401 — registers all models with Base.metadata
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.security import hash_password
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.challenge import Challenge
from app.models.leaderboard import LeaderboardEntry
from app.models.submission import Submission
from app.models.user import User

_VALID_PASSWORD = "Str0ng!P@ssw0rd"


# ── Test app factory ───────────────────────────────────────────────────────────


def _build_test_app(tmp_path, monkeypatch):
    from app import main as main_module
    from app.core.config import get_settings
    from app.db import session as session_module

    # Disable inline eval so background tasks don't hit the OpenAI API in tests
    monkeypatch.setenv("PROMPTCODE_SUBMISSION_INLINE_QUEUE_PROCESSING", "false")

    db_file = tmp_path / "sub_test.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _create_schema():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())

    async def override_get_db():
        async with session_factory() as session:
            yield session

    monkeypatch.setattr(session_module, "engine", test_engine)
    monkeypatch.setattr(session_module, "async_session_factory", session_factory)
    monkeypatch.setattr(main_module, "engine", test_engine)
    get_settings.cache_clear()

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return app, test_engine, session_factory


def _teardown(app, test_engine):
    from app.core.config import get_settings
    get_settings.cache_clear()
    app.dependency_overrides.clear()
    asyncio.run(test_engine.dispose())


def _signup(client, *, email, username):
    r = client.post(
        "/api/auth/signup",
        json={"email": email, "username": username, "password": _VALID_PASSWORD},
    )
    assert r.status_code == 201
    return r.json()["access_token"]


async def _insert_challenge(session_factory) -> uuid.UUID:
    challenge_id = uuid.uuid4()
    async with session_factory() as db:
        db.add(Challenge(
            id=challenge_id,
            slug=f"test-{challenge_id.hex[:8]}",
            title="Test Challenge",
            description="Integration test challenge.",
        ))
        await db.commit()
    return challenge_id


# ── Submissions ────────────────────────────────────────────────────────────────


def test_create_submission_requires_auth(tmp_path, monkeypatch):
    app, engine, sf = _build_test_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        r = client.post(
            "/api/submissions/",
            json={"challenge_id": str(uuid.uuid4()), "code": "print('hi')"},
        )
        assert r.status_code == 401
    _teardown(app, engine)


def test_create_submission_unknown_challenge(tmp_path, monkeypatch):
    app, engine, sf = _build_test_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        token = _signup(client, email="s1@x.com", username="subtest001")
        r = client.post(
            "/api/submissions/",
            json={"challenge_id": str(uuid.uuid4()), "code": "print('hi')"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 404
    _teardown(app, engine)


def test_create_submission_invalid_entrypoints(tmp_path, monkeypatch):
    app, engine, sf = _build_test_app(tmp_path, monkeypatch)
    challenge_id = asyncio.run(_insert_challenge(sf))
    with TestClient(app) as client:
        token = _signup(client, email="s2@x.com", username="subtest002")
        headers = {"Authorization": f"Bearer {token}"}
        for bad in ["../escape.py", "/abs.py", "subdir/nested.py", "noext", ""]:
            r = client.post(
                "/api/submissions/",
                json={"challenge_id": str(challenge_id), "code": "x=1", "entrypoint": bad or "x"},
                headers=headers,
            )
            assert r.status_code == 400, f"expected 400 for entrypoint={bad!r}, got {r.status_code}"
    _teardown(app, engine)


def test_create_submission_happy_path(tmp_path, monkeypatch):
    app, engine, sf = _build_test_app(tmp_path, monkeypatch)
    challenge_id = asyncio.run(_insert_challenge(sf))
    with TestClient(app) as client:
        token = _signup(client, email="s3@x.com", username="subtest003")
        r = client.post(
            "/api/submissions/",
            json={"challenge_id": str(challenge_id), "code": "print('hello')", "entrypoint": "main.py"},
            headers={"Authorization": f"Bearer {token}"},
        )
        assert r.status_code == 201
        data = r.json()
        assert data["challenge_id"] == str(challenge_id)
        assert data["status"] == "pending"
        assert data["entrypoint"] == "main.py"
        assert uuid.UUID(data["id"])  # valid UUID
    _teardown(app, engine)


def test_list_submissions_scoped_to_user(tmp_path, monkeypatch):
    app, engine, sf = _build_test_app(tmp_path, monkeypatch)
    challenge_id = asyncio.run(_insert_challenge(sf))
    with TestClient(app) as client:
        token_a = _signup(client, email="sa@x.com", username="subtest004a")
        token_b = _signup(client, email="sb@x.com", username="subtest004b")
        # User A creates a submission
        client.post(
            "/api/submissions/",
            json={"challenge_id": str(challenge_id), "code": "x=1"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        # User A sees 1, User B sees 0
        r_a = client.get("/api/submissions/", headers={"Authorization": f"Bearer {token_a}"})
        r_b = client.get("/api/submissions/", headers={"Authorization": f"Bearer {token_b}"})
        assert r_a.status_code == 200
        assert len(r_a.json()) == 1
        assert r_b.status_code == 200
        assert r_b.json() == []
    _teardown(app, engine)


def test_get_submission_forbidden_for_other_user(tmp_path, monkeypatch):
    app, engine, sf = _build_test_app(tmp_path, monkeypatch)
    challenge_id = asyncio.run(_insert_challenge(sf))
    with TestClient(app) as client:
        token_a = _signup(client, email="sc@x.com", username="subtest005a")
        token_b = _signup(client, email="sd@x.com", username="subtest005b")
        r = client.post(
            "/api/submissions/",
            json={"challenge_id": str(challenge_id), "code": "x=1"},
            headers={"Authorization": f"Bearer {token_a}"},
        )
        sub_id = r.json()["id"]
        # User B cannot fetch User A's submission
        r_b = client.get(
            f"/api/submissions/{sub_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert r_b.status_code == 403
    _teardown(app, engine)


# ── Leaderboard ────────────────────────────────────────────────────────────────


def test_leaderboard_empty_for_unknown_challenge(tmp_path, monkeypatch):
    app, engine, sf = _build_test_app(tmp_path, monkeypatch)
    with TestClient(app) as client:
        r = client.get(f"/api/leaderboard/{uuid.uuid4()}")
        assert r.status_code == 200
        assert r.json() == []
    _teardown(app, engine)


async def _seed_leaderboard(session_factory, n: int = 3) -> uuid.UUID:
    """Insert challenge, users, submissions, and leaderboard entries directly."""
    challenge_id = uuid.uuid4()
    async with session_factory() as db:
        db.add(Challenge(
            id=challenge_id,
            slug=f"lb-{challenge_id.hex[:8]}",
            title="LB Challenge",
            description="test",
        ))
        await db.flush()
        for i in range(n):
            user_id = uuid.uuid4()
            sub_id = uuid.uuid4()
            db.add(User(
                id=user_id,
                email=f"lbuser{i}_{challenge_id.hex[:6]}@example.com",
                username=f"lbu{challenge_id.hex[:6]}{i}",
                password_hash=hash_password("dummy-pass"),
            ))
            await db.flush()
            db.add(Submission(
                id=sub_id,
                challenge_id=challenge_id,
                user_id=user_id,
                code="x=1",
                status="completed",
            ))
            await db.flush()
            db.add(LeaderboardEntry(
                challenge_id=challenge_id,
                user_id=user_id,
                submission_id=sub_id,
                score_overall=float(n - i),  # descending: n, n-1, ..., 1
            ))
        await db.commit()
    return challenge_id


def test_leaderboard_response_shape(tmp_path, monkeypatch):
    app, engine, sf = _build_test_app(tmp_path, monkeypatch)
    challenge_id = asyncio.run(_seed_leaderboard(sf, n=1))
    with TestClient(app) as client:
        r = client.get(f"/api/leaderboard/{challenge_id}")
        assert r.status_code == 200
        entries = r.json()
        assert len(entries) == 1
        e = entries[0]
        assert e["rank"] == 1
        assert isinstance(e["username"], str) and e["username"] != ""
        assert isinstance(e["score_overall"], float)
        assert "submission_id" in e
        assert "user_id" in e
    _teardown(app, engine)


def test_leaderboard_pagination(tmp_path, monkeypatch):
    app, engine, sf = _build_test_app(tmp_path, monkeypatch)
    challenge_id = asyncio.run(_seed_leaderboard(sf, n=3))
    with TestClient(app) as client:
        # Full list — ordered by score desc
        r_all = client.get(f"/api/leaderboard/{challenge_id}?limit=10&offset=0")
        assert r_all.status_code == 200
        all_entries = r_all.json()
        assert len(all_entries) == 3
        assert all_entries[0]["rank"] == 1
        assert all_entries[0]["score_overall"] >= all_entries[1]["score_overall"]

        # Limit to 2
        r_limited = client.get(f"/api/leaderboard/{challenge_id}?limit=2&offset=0")
        assert len(r_limited.json()) == 2

        # Offset 1 — skip top entry, rank starts at 2
        r_offset = client.get(f"/api/leaderboard/{challenge_id}?limit=10&offset=1")
        offset_entries = r_offset.json()
        assert len(offset_entries) == 2
        assert offset_entries[0]["rank"] == 2
    _teardown(app, engine)
