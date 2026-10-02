"""Assistant proposals stay visible, refuse protected files, and match the workspace."""

from __future__ import annotations

import asyncio

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.services.interview.ai_provider import AIResponse
from app.services.interview.assistant_changes import reconcile_assistant_proposals

_PASSWORD = "Str0ng!P@ssw0rd"


def test_reconcile_refuses_protected_files_and_unlisted_claims(tmp_path):
    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "app").mkdir()
    (workspace / "app" / "service.py").write_text("def place():\n    return 1\n", encoding="utf-8")
    (workspace / "tests").mkdir()
    (workspace / "tests" / "test_orders.py").write_text("def test_keep():\n    assert True\n", encoding="utf-8")
    reply = (
        "I changed tests/test_orders.py and app/service.py. I also created app/ghost.py.\n\n"
        "```python\n# file: tests/test_orders.py\ndef test_hacked():\n    assert False\n```\n\n"
        "```python\n# file: app/service.py\ndef place():\n    return 2\n```\n"
    )
    cleaned, kept, refused = reconcile_assistant_proposals(
        reply=reply,
        proposed=[],
        workspace=workspace,
    )
    # fences are parsed by the route; pass them as proposed here
    proposed = [
        {"path": "tests/test_orders.py", "content": "def test_hacked():\n    assert False\n"},
        {"path": "app/service.py", "content": "def place():\n    return 2\n"},
    ]
    cleaned, kept, refused = reconcile_assistant_proposals(
        reply=reply,
        proposed=proposed,
        workspace=workspace,
    )
    assert [item["path"] for item in kept] == ["app/service.py"]
    assert "return 2" in kept[0]["unified"]
    assert refused == [{"path": "tests/test_orders.py", "reason": "This file is read-only."}]
    assert "Refused" in cleaned
    assert "tests/test_orders.py" in cleaned
    assert "nothing is written until you accept" in cleaned.lower()
    assert "def test_hacked" not in cleaned
    assert "app/ghost.py" in cleaned
    assert "not in the workspace change list" in cleaned
    assert (workspace / "app" / "service.py").read_text(encoding="utf-8").startswith("def place():\n    return 1")


def _build_test_app(tmp_path, monkeypatch):
    from app import main as main_module
    from app.core.config import get_settings
    from app.db import session as session_module

    monkeypatch.setenv("PROMPTCODE_DEBUG", "true")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "test-only-secret-not-used-in-prod")
    monkeypatch.setenv("PROMPTCODE_AI_PROVIDER", "mock")
    get_settings.cache_clear()
    db_file = tmp_path / "assistant.db"
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


def test_apply_records_assistant_source_and_matches_workspace(tmp_path, monkeypatch):
    class Stub:
        async def complete_request(self, request):
            return AIResponse(
                text=(
                    "I updated app/service.py, deleted tests/test_orders.py, and created app/ghost.py.\n\n"
                    "```python\n# file: app/service.py\n# assistant-marker\n"
                    "def place():\n    return 1\n```\n\n"
                    "```python\n# file: tests/test_orders.py\n# nope\n```\n"
                ),
                provider="stub",
                model="stub",
            )

    monkeypatch.setattr(
        "app.api.routes.interview.get_ai_provider",
        lambda: Stub(),
    )
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            signup = client.post(
                "/api/auth/signup",
                json={
                    "email": "assistant@example.com",
                    "username": "assistantuser",
                    "password": _PASSWORD,
                    "first_name": "AI",
                    "last_name": "User",
                },
            )
            assert signup.status_code == 201, signup.text
            headers = {"Authorization": f"Bearer {signup.json()['access_token']}"}
            start = client.post(
                "/api/interview/sessions",
                headers=headers,
                json={"challenge_slug": "order-hold-reason"},
            )
            assert start.status_code == 200, start.text
            sid = start.json()["id"]
            chat = client.post(
                f"/api/interview/sessions/{sid}/ai/chat",
                headers=headers,
                json={"message": "please edit the service"},
            )
            assert chat.status_code == 200, chat.text
            body = chat.json()
            assert [item["path"] for item in body["proposed_edits"]] == ["app/service.py"]
            assert "assistant-marker" in body["proposed_edits"][0]["unified"]
            assert body["refused_edits"][0]["path"] == "tests/test_orders.py"
            assert "Refused" in body["reply"]
            assert "not in the workspace change list" in body["reply"]
            edit = body["proposed_edits"][0]
            applied = client.post(
                f"/api/interview/sessions/{sid}/ai/apply",
                headers=headers,
                json={
                    "path": edit["path"],
                    "content": edit["content"],
                    "disposition": "accepted",
                    "base_revision": edit["base_revision"],
                },
            )
            assert applied.status_code == 200, applied.text
            assert applied.json()["content"] == edit["content"]
            stored = client.get(
                f"/api/interview/sessions/{sid}/files/app/service.py",
                headers=headers,
            )
            assert stored.json()["content"] == edit["content"]
            events = client.get(f"/api/interview/sessions/{sid}/events", headers=headers)
            changed = [
                event for event in events.json()
                if event["event_type"] == "file_changed" and event["payload"].get("source") == "assistant"
            ]
            assert changed
            assert changed[-1]["created_at"]
            assert changed[-1]["payload"]["path"] == "app/service.py"
    finally:
        from app.core.config import get_settings

        get_settings.cache_clear()
        app.dependency_overrides.clear()
        asyncio.run(test_engine.dispose())
