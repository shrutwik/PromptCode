"""Cross-layer integration checks from the full product audit.

Covers defend answer-guide leakage, feedback field passthrough, and event order.
"""

from __future__ import annotations

import asyncio
import threading
from pathlib import Path

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


def test_slow_workspace_creation_does_not_block_other_requests(tmp_path, monkeypatch):
    from httpx import ASGITransport, AsyncClient

    from app.api.routes import interview
    from app.core.config import get_settings
    monkeypatch.setenv("PROMPTCODE_INTERVIEW_WORKSPACE_ROOT", str(tmp_path / "workspaces"))
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    entered, release = threading.Event(), threading.Event()
    original = interview.create_workspace
    def slow_create(*args):
        entered.set()
        assert release.wait(3), "Workspace copy blocked the event loop"
        return original(*args)
    monkeypatch.setattr(interview, "create_workspace", slow_create)
    async def exercise():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            signup = await client.post("/api/auth/signup", json={
                "email": "responsive@example.com", "username": "responsive",
                "password": _PASSWORD, "first_name": "Beta", "last_name": "User"})
            assert signup.status_code == 201
            headers = {"Authorization": "Bearer " + signup.json()["access_token"]}
            pending = asyncio.create_task(client.post("/api/interview/sessions",
                headers=headers, json={"challenge_slug": "order-hold-reason"}))
            try:
                assert await asyncio.to_thread(entered.wait, 1)
                assert not pending.done(), "Slow filesystem work ran on the event loop"
                health = await asyncio.wait_for(client.get("/health"), .5)
                assert health.status_code == 200
            finally:
                release.set()
            assert (await pending).status_code == 200
        await test_engine.dispose()
    try:
        asyncio.run(exercise())
    finally:
        release.set()
        get_settings.cache_clear()


def test_candidate_defend_questions_never_include_answer_keys():
    for slug_q in candidate_defend_questions("invoice-status-transition"):
        q = slug_q["question"]
        assert "answer_guide" not in slug_q
        assert " A:" not in q
        assert not q.rstrip().endswith("A:")
    parsed = parse_defend_questions("invoice-status-transition")
    assert all(p.get("answer_guide") for p in parsed), "guides must remain server-side"


def test_defend_and_feedback_integration(tmp_path, monkeypatch):
    from app.api.routes import interview as route
    from app.services.interview.ai_provider import MockAIProvider

    monkeypatch.setattr(route, "get_ai_provider", MockAIProvider)
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

            for event_type in ("test_result", "ai_response", "file_changed", "defend_answer", "submission"):
                forged = client.post(f"/api/interview/sessions/{sid}/events", headers=headers,
                                     json={"event_type": event_type, "payload": {"ok": True}})
                assert forged.status_code == 400
            bad_search = client.post(f"/api/interview/sessions/{sid}/events", headers=headers,
                                     json={"event_type": "file_searched", "payload": {"query": "x", "hits": True}})
            assert bad_search.status_code == 400

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
            assessment = submit.json()["assessment"]
            assert assessment["status"] == "pending_review"
            assert assessment["total_score"] is None
            assert assessment["packet"]["session_id"] == sid
            assert submit.json()["scoring_version"] == "v4-research-pilot"
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

            for invalid in ({"index": -1, "answer": "x"}, {"index": 99, "answer": "x"},
                            {"index": 0, "answer": " "}, {"index": 0, "answer": "x" * 4001}):
                result = client.post(f"/api/interview/sessions/{sid}/defend", headers=headers, json=invalid)
                assert result.status_code in (400, 422)
            answered = client.post(f"/api/interview/sessions/{sid}/defend", headers=headers,
                                   json={"index": 0, "answer": "I rejected this proposed fix."})
            assert answered.status_code == 200, answered.text
            updated = client.get(f"/api/interview/sessions/{sid}/report", headers=headers).json()
            assert updated["assessment"]["packet_digest"] != assessment["packet_digest"]
            assert updated["assessment"]["total_score"] is None
            assert "answer_guides" not in updated["metrics"]
            assert updated["assessment"]["packet"]["evidence"][-1]["id"] == "defend:0"
            dashboard = client.get("/api/interview/dashboard", headers=headers).json()
            assert dashboard["avg_score"] is None
            assert dashboard["sessions"][0]["total_score"] is None
            assert dashboard["trends"] == []

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


def test_deepseek_question_hint_execution_submission_workflow(tmp_path, monkeypatch):
    import json
    import os

    import httpx

    from app.api.routes import interview as route
    from app.services.interview.ai_provider import ProductionAIProvider
    calls = []
    def respond(request):
        payload = json.loads(request.content)
        calls.append(payload)
        assert payload['model'] == 'deepseek-flash'
        assert payload['max_tokens'] == 600
        assert payload['thinking'] == {'type': 'disabled'}
        assert sum(len(m['content']) for m in payload['messages']) <= 18000
        assert 'README.md' in payload['messages'][1]['content']
        content = 'Check what the failing assertion expects.' if len(calls) == 1 else '{"allowed": true}'
        return httpx.Response(200, json={'model': 'deepseek-flash', 'choices': [{'message': {'content': content}}], 'usage': {'prompt_tokens': 3000, 'completion_tokens': 12}})
    original = httpx.AsyncClient
    # Test-only local execution; production continues to require Docker.
    monkeypatch.setenv('PROMPTCODE_ALLOW_UNSAFE_LOCAL_RUNNER', '1')
    monkeypatch.setenv('PATH', str(Path(__file__).resolve().parents[2] / '.venv/bin') + os.pathsep + os.environ['PATH'])
    monkeypatch.setenv('DEEPSEEK_API_KEY', 'test-only-deepseek-key')
    monkeypatch.setenv('PROMPTCODE_AI_BASE_URL', 'https://api.deepseek.com')
    monkeypatch.setenv('PROMPTCODE_AI_MODEL', 'deepseek-flash')
    monkeypatch.setattr(httpx, 'AsyncClient', lambda **kwargs: original(transport=httpx.MockTransport(respond), **kwargs))
    monkeypatch.setattr(route, 'get_ai_provider', ProductionAIProvider)
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            user = _signup(client, email='deepseek-flow@example.com', username='deepseekflow')
            headers = {'Authorization': f"Bearer {user['access_token']}"}
            start = client.post('/api/interview/sessions', headers=headers, json={'challenge_slug': 'order-hold-reason'})
            assert start.status_code == 200, start.text
            sid = start.json()['id']
            headers['X-Session-Token'] = start.json()['owner_token']
            off_topic = client.post(f'/api/interview/sessions/{sid}/ai/chat', headers=headers, json={'message': 'Tell me about cats'})
            assert off_topic.status_code == 200, off_topic.text
            assert off_topic.json()['provider'] == 'guardrail'
            assert calls == []
            hint = client.post(f'/api/interview/sessions/{sid}/ai/chat', headers=headers, json={'message': 'Why does this test fail?'})
            assert hint.status_code == 200, hint.text
            assert hint.json()['model'] == 'deepseek-flash'
            assert len(calls) == 2  # draft plus independent semantic review
            assert hint.json()['reply'] == 'Check what the failing assertion expects.'
            # Editing remains an explicit candidate action.
            path = 'app/service.py'
            original_file = client.get(f'/api/interview/sessions/{sid}/files/{path}', headers=headers)
            assert original_file.status_code == 200
            saved = client.put(f'/api/interview/sessions/{sid}/files/{path}', headers=headers, json={'content': original_file.json()['content'] + '\n# candidate reviewed hint\n'})
            assert saved.status_code == 200, saved.text
            execution = client.post(f'/api/interview/sessions/{sid}/tests', headers=headers, json={'command_id': 'run_tests'})
            assert execution.status_code == 200, execution.text
            assert execution.json()['error_code'] is None, execution.text
            assert not execution.json()['timed_out'], execution.text
            assert execution.json()['counts']['total'] > 0, execution.text
            submitted = client.post(f'/api/interview/sessions/{sid}/submit', headers=headers, json={})
            assert submitted.status_code == 200, submitted.text
            for question in submitted.json()['defend_questions']:
                assert 'answer_guide' not in question
    finally:
        asyncio.run(test_engine.dispose())
