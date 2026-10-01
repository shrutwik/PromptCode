"""Cross-layer integration checks from the full product audit.

Covers defend answer-guide leakage, feedback field passthrough, and event order.
"""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.services.interview.rubric import (
    candidate_defend_questions,
    parse_defend_questions,
    sanitize_candidate_question,
)

_PASSWORD = "Str0ng!P@ssw0rd"


def _build_test_app(tmp_path, monkeypatch):
    from app import main as main_module
    from app.core.config import get_settings
    from app.db import session as session_module

    monkeypatch.setenv("PROMPTCODE_DEBUG", "true")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "test-only-secret-not-used-in-prod")
    monkeypatch.setenv("PROMPTCODE_RUNNER", "local")
    get_settings.cache_clear()

    db_file = tmp_path / "interview_integ_audit.db"
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


def test_sanitize_strips_inline_answer_keys():
    assert "A:" not in sanitize_candidate_question("1. Q: Why not timezone? A: Not on path.")
    assert "?" in sanitize_candidate_question("1. Q: Why not timezone? A: Not on path.")


def test_candidate_defend_questions_never_include_answer_keys():
    for slug_q in candidate_defend_questions("invoice-status-transition"):
        q = slug_q["question"]
        assert "answer_guide" not in slug_q
        assert " A:" not in q
        assert not q.rstrip().endswith("A:")
    parsed = parse_defend_questions("invoice-status-transition")
    assert all(p.get("answer_guide") for p in parsed), "guides must remain server-side"


def test_defend_and_feedback_integration(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            challenges = client.get("/api/interview/challenges")
            assert challenges.status_code == 200
            slug = challenges.json()[0]["slug"]

            user = _signup(client, email="integ@example.com", username="integaudit")
            headers = {"Authorization": f"Bearer {user['access_token']}"}

            start = client.post(
                "/api/interview/sessions",
                headers=headers,
                json={"challenge_slug": slug},
            )
            assert start.status_code == 200, start.text
            sid = start.json()["id"]
            headers = {
                **headers,
                "X-Session-Token": start.json()["owner_token"],
            }

            files = client.get(f"/api/interview/sessions/{sid}/files", headers=headers)
            assert files.status_code == 200
            payload = files.json()
            file_list = payload.get("files") if isinstance(payload, dict) else payload
            paths = [
                f["path"] if isinstance(f, dict) else f for f in file_list
            ]
            src = next(
                (
                    p
                    for p in paths
                    if p.endswith((".ts", ".tsx", ".py")) and "test" not in p.lower()
                ),
                paths[0],
            )
            got = client.get(
                f"/api/interview/sessions/{sid}/files/{src}", headers=headers
            )
            assert got.status_code == 200
            content = got.json()["content"]
            saved = client.put(
                f"/api/interview/sessions/{sid}/files/{src}",
                headers=headers,
                json={"content": content + "\n// audit\n"},
            )
            assert saved.status_code == 200

            client.post(
                f"/api/interview/sessions/{sid}/tests",
                headers=headers,
                json={"command_id": "run_tests"},
            )
            client.post(
                f"/api/interview/sessions/{sid}/ai/chat",
                headers=headers,
                json={"message": "Summarize this file", "attached_paths": [src]},
            )

            submit = client.post(
                f"/api/interview/sessions/{sid}/submit", headers=headers, json={}
            )
            assert submit.status_code == 200, submit.text
            for q in submit.json()["defend_questions"]:
                assert "answer_guide" not in q
                assert " A:" not in q["question"]

            defend = client.get(
                f"/api/interview/sessions/{sid}/defend", headers=headers
            )
            assert defend.status_code == 200
            for q in defend.json()["questions"]:
                assert "answer_guide" not in q
                assert " A:" not in q["question"]

            fb = client.post(
                f"/api/interview/sessions/{sid}/feedback",
                headers=headers,
                json={
                    "realism": 4,
                    "difficulty": 3,
                    "text": "notes",
                    "ai_as_expected": 5,
                    "confusing_or_broken": True,
                    "most_like_real_interview": False,
                },
            )
            assert fb.status_code == 200, fb.text

            events = client.get(
                f"/api/interview/sessions/{sid}/events", headers=headers
            )
            assert events.status_code == 200
            types = [e["event_type"] for e in events.json()]
            assert types[0] == "session_started"
            assert "file_changed" in types
            assert "submission" in types
            # Chronological: session_started must precede later work
            assert types.index("session_started") < types.index("file_changed")
            assert types.index("file_changed") < types.index("submission")
    finally:
        asyncio.run(test_engine.dispose())
