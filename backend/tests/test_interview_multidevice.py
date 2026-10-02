"""Bearer resume without owner token, and interviewer-only defend guides."""

from __future__ import annotations

import asyncio
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.models.interview_session import InterviewEvaluation, InterviewSession
from app.models.user import User
from app.services.interview.rubric import parse_defend_questions

_PASSWORD = "Str0ng!P@ssw0rd"


def _build_test_app(tmp_path, monkeypatch):
    from app import main as main_module
    from app.core.config import get_settings
    from app.db import session as session_module

    monkeypatch.setenv("PROMPTCODE_DEBUG", "true")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "test-only-secret-not-used-in-prod")
    get_settings.cache_clear()

    db_file = tmp_path / "interview_multidevice.db"
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
    return app, test_engine


def _signup(client: TestClient, *, email: str, username: str) -> dict:
    r = client.post(
        "/api/auth/signup",
        json={
            "email": email,
            "username": username,
            "password": _PASSWORD,
            "first_name": "Beta",
            "last_name": "User",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _cleanup(app, test_engine):
    from app.core.config import get_settings

    get_settings.cache_clear()
    app.dependency_overrides.clear()
    asyncio.run(test_engine.dispose())


def test_second_client_bearer_without_owner_token(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as starter:
            slug = starter.get("/api/interview/challenges").json()[0]["slug"]
            owner = _signup(starter, email="owner@example.com", username="device_owner")
            other = _signup(starter, email="other@example.com", username="device_other")
            start = starter.post(
                "/api/interview/sessions",
                headers={"Authorization": f"Bearer {owner['access_token']}"},
                json={"challenge_slug": slug},
            )
            assert start.status_code == 200, start.text
            sid = start.json()["id"]
            owner_token = start.json()["owner_token"]

        bearer = {"Authorization": f"Bearer {owner['access_token']}"}
        with TestClient(app) as second:
            assert "X-Session-Token" not in bearer
            got = second.get(f"/api/interview/sessions/{sid}", headers=bearer)
            assert got.status_code == 200, got.text
            assert got.json()["id"] == sid
            wrote = second.post(
                f"/api/interview/sessions/{sid}/events",
                headers=bearer,
                json={"event_type": "file_searched", "payload": {"query": "resume"}},
            )
            assert wrote.status_code == 200, wrote.text

        other_headers = {
            "Authorization": f"Bearer {other['access_token']}",
            "X-Session-Token": owner_token,
        }
        with TestClient(app) as stranger:
            missing = stranger.get(f"/api/interview/sessions/{sid}", headers=other_headers)
            assert missing.status_code == 404, missing.text
    finally:
        _cleanup(app, test_engine)


def test_interviewer_defend_guides_hidden_from_candidates(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            slug = client.get("/api/interview/challenges").json()[0]["slug"]
            user = _signup(client, email="guide@example.com", username="guide_user")
            headers = {"Authorization": f"Bearer {user['access_token']}"}
            start = client.post(
                "/api/interview/sessions",
                headers=headers,
                json={"challenge_slug": slug},
            )
            assert start.status_code == 200, start.text
            sid = start.json()["id"]
            guides = parse_defend_questions(slug)

            async def _seed():
                async with test_engine.begin() as conn:
                    await conn.execute(
                        InterviewSession.__table__.update()
                        .where(InterviewSession.id == uuid.UUID(sid))
                        .values(status="submitted")
                    )
                    await conn.execute(
                        InterviewEvaluation.__table__.insert().values(
                            id=uuid.uuid4(),
                            session_id=uuid.UUID(sid),
                            total_score=1.0,
                            rubric={},
                            metrics={"answer_guides": guides, "defend_answers": {}},
                            insights=[],
                            test_summary={},
                            defend_questions=[
                                {"question": item["question"], "index": i}
                                for i, item in enumerate(guides)
                            ],
                            scoring_version="v2",
                        )
                    )

            asyncio.run(_seed())
            candidate = client.get(f"/api/interview/sessions/{sid}/defend", headers=headers)
            assert candidate.status_code == 200, candidate.text
            assert candidate.json()["questions"]
            assert all("answer_guide" not in q for q in candidate.json()["questions"])
            report = client.get(f"/api/interview/sessions/{sid}/report", headers=headers)
            assert report.status_code == 200, report.text
            assert all("answer_guide" not in q for q in report.json()["defend_questions"])
            assert "answer_guides" not in (report.json().get("metrics") or {})

            async def _promote():
                async with test_engine.begin() as conn:
                    await conn.execute(
                        User.__table__.update()
                        .where(User.email == "guide@example.com")
                        .values(role="interviewer")
                    )

            asyncio.run(_promote())
            interviewer = client.get(f"/api/interview/sessions/{sid}/defend", headers=headers)
            assert interviewer.status_code == 200, interviewer.text
            texts = [q.get("answer_guide") for q in interviewer.json()["questions"]]
            assert any(texts)
            assert all(text for text in texts)
    finally:
        _cleanup(app, test_engine)
