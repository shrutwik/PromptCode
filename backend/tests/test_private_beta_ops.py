"""Private-beta invite gate, analytics, calibration, versions."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app

_PASSWORD = "Str0ng!P@ssw0rd"


def _build_test_app(tmp_path, monkeypatch, *, invite_required: bool = False):
    from app import main as main_module
    from app.core.config import get_settings
    from app.db import session as session_module

    monkeypatch.setenv("PROMPTCODE_DEBUG", "true")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "test-only-secret-not-used-in-prod")
    monkeypatch.setenv(
        "PROMPTCODE_BETA_INVITE_REQUIRED", "true" if invite_required else "false"
    )
    monkeypatch.setenv("PROMPTCODE_INTERVIEW_INTERNAL_TOKEN", "test-internal")
    get_settings.cache_clear()

    db_file = tmp_path / "beta_ops.db"
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

    app = create_app()
    app.dependency_overrides[get_db] = override_get_db
    return app, test_engine, session_factory


def test_invite_required_blocks_without_code(tmp_path, monkeypatch):
    app, engine, _ = _build_test_app(tmp_path, monkeypatch, invite_required=True)
    try:
        with TestClient(app) as client:
            r = client.post(
                "/api/auth/signup",
                json={
                    "email": "noinvite@example.com",
                    "username": "noinvite_user",
                    "password": _PASSWORD,
                    "first_name": "N",
                    "last_name": "I",
                },
            )
            assert r.status_code == 403
            assert "Invite required" in r.json()["detail"]
            # No config leak
            assert "allowlist" not in r.text.lower()
            assert "invite_codes" not in r.text.lower()
    finally:
        asyncio.run(engine.dispose())


def test_invite_code_signup_and_analytics(tmp_path, monkeypatch):
    app, engine, factory = _build_test_app(tmp_path, monkeypatch, invite_required=True)
    try:
        from app.services.interview.beta_access import create_invite

        async def _invite():
            async with factory() as db:
                return await create_invite(db, cohort="wave1", max_uses=1, code="BETA-TEST-1")

        invite = asyncio.run(_invite())
        with TestClient(app) as client:
            bad = client.post(
                "/api/auth/signup",
                json={
                    "email": "bad@example.com",
                    "username": "bad_user_x",
                    "password": _PASSWORD,
                    "invite_code": "WRONG",
                },
            )
            assert bad.status_code == 403

            ok = client.post(
                "/api/auth/signup",
                json={
                    "email": "invited@example.com",
                    "username": "invited_user",
                    "password": _PASSWORD,
                    "first_name": "In",
                    "last_name": "Vite",
                    "invite_code": invite.code,
                },
            )
            assert ok.status_code == 201, ok.text
            body = ok.json()
            assert body["user"]["beta_cohort"] == "wave1"
            assert body["user"]["signup_source"] == "invite"

            headers = {"Authorization": f"Bearer {body['access_token']}"}
            client.get("/api/interview/challenges", headers=headers)
            slug = client.get("/api/interview/challenges").json()[0]["slug"]
            started = client.post(
                "/api/interview/sessions",
                json={"challenge_slug": slug},
                headers=headers,
            )
            assert started.status_code == 200, started.text
            sess = started.json()
            assert sess.get("id")

            cal = client.get(
                "/api/interview/internal/calibration",
                headers={"X-PromptCode-Internal-Token": "test-internal"},
            )
            assert cal.status_code == 200
            funnel = client.get(
                "/api/interview/internal/analytics/funnel",
                headers={"X-PromptCode-Internal-Token": "test-internal"},
            )
            assert funnel.status_code == 200
            assert funnel.json()["counts"].get("user_signed_up", 0) >= 1
            assert funnel.json()["counts"].get("session_started", 0) >= 1

            # Second use of single-use invite fails
            again = client.post(
                "/api/auth/signup",
                json={
                    "email": "second@example.com",
                    "username": "second_user",
                    "password": _PASSWORD,
                    "invite_code": invite.code,
                },
            )
            assert again.status_code == 403
    finally:
        asyncio.run(engine.dispose())


def test_internal_routes_stay_closed_when_debug_is_on(tmp_path, monkeypatch):
    app, engine, _ = _build_test_app(tmp_path, monkeypatch, invite_required=False)
    try:
        with TestClient(app) as client:
            missing = client.get("/api/interview/internal/users")
            wrong = client.get(
                "/api/interview/internal/users",
                headers={"X-PromptCode-Internal-Token": "not-the-token"},
            )
            ok = client.get(
                "/api/interview/internal/users",
                headers={"X-PromptCode-Internal-Token": "test-internal"},
            )
        assert missing.status_code == 404
        assert wrong.status_code == 404
        assert ok.status_code == 200
    finally:
        asyncio.run(engine.dispose())


def test_disable_blocks_login_and_sessions(tmp_path, monkeypatch):
    app, engine, _ = _build_test_app(tmp_path, monkeypatch, invite_required=False)
    try:
        with TestClient(app) as client:
            su = client.post(
                "/api/auth/signup",
                json={
                    "email": "dis@example.com",
                    "username": "dis_user",
                    "password": _PASSWORD,
                },
            )
            assert su.status_code == 201
            uid = su.json()["user"]["id"]
            token = su.json()["access_token"]
            refresh = su.json()["refresh_token"]
            dis = client.post(
                f"/api/interview/internal/users/{uid}/disable",
                headers={"X-PromptCode-Internal-Token": "test-internal"},
            )
            assert dis.status_code == 200
            login = client.post(
                "/api/auth/login",
                json={"email": "dis@example.com", "password": _PASSWORD},
            )
            assert login.status_code == 403
            # Existing token cannot start sessions
            challenges = client.get("/api/interview/challenges").json()
            slug = challenges[0]["slug"]
            start = client.post(
                "/api/interview/sessions",
                json={"challenge_slug": slug},
                headers={"Authorization": f"Bearer {token}"},
            )
            assert start.status_code == 403
            refreshed = client.post("/api/auth/refresh", json={"refresh_token": refresh})
            assert refreshed.status_code == 403
    finally:
        asyncio.run(engine.dispose())


def test_scoring_version_on_submit(tmp_path, monkeypatch):
    app, engine, _ = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            su = client.post(
                "/api/auth/signup",
                json={
                    "email": "score@example.com",
                    "username": "score_user",
                    "password": _PASSWORD,
                },
            )
            headers = {"Authorization": f"Bearer {su.json()['access_token']}"}
            slug = client.get("/api/interview/challenges").json()[0]["slug"]
            sess = client.post(
                "/api/interview/sessions",
                json={"challenge_slug": slug},
                headers=headers,
            ).json()
            assert sess["id"]
            submitted = client.post(
                f"/api/interview/sessions/{sess['id']}/submit",
                headers=headers,
            )
            assert submitted.status_code == 200, submitted.text
            report = submitted.json()
            # Reference the canonical constant: a literal here silently went stale
            # when scoring moved from v2 to the evidence-based v3.
            from app.services.interview.analytics import SCORING_VERSION
            assert report["scoring_version"] == SCORING_VERSION
            assert report.get("challenge_version")
            fb = client.post(
                f"/api/interview/sessions/{sess['id']}/feedback",
                headers=headers,
                json={
                    "realism": 4,
                    "difficulty": 3,
                    "ai_as_expected": 4,
                    "confusing_or_broken": False,
                    "most_like_real_interview": True,
                    "text": "ok",
                },
            )
            assert fb.status_code == 200
            review = client.post(
                f"/api/interview/internal/sessions/{sess['id']}/review",
                headers={"X-PromptCode-Internal-Token": "test-internal"},
                json={
                    "notes": "looks fair",
                    "disagreement": False,
                    "category_observations": {"correctness": "ok"},
                },
            )
            assert review.status_code == 200
            payload = client.get(
                f"/api/interview/internal/sessions/{sess['id']}/review",
                headers={"X-PromptCode-Internal-Token": "test-internal"},
            )
            assert payload.status_code == 200
            assert "automated_score" in payload.json()
            assert payload.json()["human_reviews"]
    finally:
        asyncio.run(engine.dispose())
