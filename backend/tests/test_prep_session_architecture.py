"""Practice-session architecture: revision, instructions, v2 score, comparison, defend."""

from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

import app.models  # noqa: F401
from app.db.base import Base
from app.db.session import get_db
from app.main import create_app
from app.services.interview.ai_provider import SYSTEM_PROMPT
from app.services.interview.levels import level_view
from app.services.interview.rubric import (
    append_accepted_defend_question,
    previous_attempt_for,
    score_session_v2,
)

_PASSWORD = "Str0ng!P@ssw0rd"
_ROOT = Path(__file__).resolve().parents[2]


def test_system_prompt_withholds_bug_and_later_steps():
    text = SYSTEM_PROMPT.lower()
    assert "do not name the bug" in text
    assert "root cause" in text
    assert "line to change" in text
    assert "whole step" in text
    assert "close and wrong" in text
    assert "solution" in text
    assert "hidden test" in text
    assert "have not reached" in text


def test_ticket_says_the_assistant_can_be_wrong():
    js = (_ROOT / "frontend/js/pages/interview-session.js").read_text(encoding="utf-8")
    assert "The assistant can be wrong." in js


def test_earlier_steps_stay_visible_and_later_steps_do_not():
    first = level_view("invoice-status-transition", 0, tests_on_step=0)
    assert first["earlier"] == []
    assert "409" not in first["body"]
    second = level_view("invoice-status-transition", 1, tests_on_step=0)
    assert second["earlier"][0]["title"] == first["title"]
    assert "409" not in second["body"]
    assert all("409" not in step["body"] for step in second["earlier"])


def test_v2_judgment_comes_from_events_not_a_model():
    events = [
        {"event_type": "file_viewed", "payload": {"path": "src/statusMachine.ts"}},
        {
            "event_type": "file_changed",
            "payload": {"path": "src/statusMachine.ts", "bytes": 200, "source": "candidate"},
        },
        {"event_type": "test_result", "payload": {"ok": False}},
        {"event_type": "ai_edit_rejected", "payload": {"path": "src/timezoneFormat.ts"}},
        {
            "event_type": "file_changed",
            "payload": {"path": "src/statusMachine.ts", "bytes": 40, "source": "candidate"},
        },
        {"event_type": "test_result", "payload": {"ok": True}},
        {
            "event_type": "defend_answer",
            "payload": {"answer": "I rejected the timezone edit and kept the status guard."},
        },
    ]
    scored = score_session_v2(
        events=events,
        test_summary={"ok": True},
        challenge_slug="invoice-status-transition",
    )
    rubric = scored["rubric"]
    assert rubric["A_correctness"] == {
        "score": 25.0,
        "max": 25,
        "evidence": rubric["A_correctness"]["evidence"],
    }
    assert rubric["A_correctness"]["score"] == 25.0
    assert rubric["B_investigation"]["score"] == 15.0
    assert rubric["B_investigation"]["max"] == 15
    assert rubric["C_fix_quality"]["score"] == 8.0
    assert rubric["C_fix_quality"]["max"] == 10
    assert rubric["D_ai_leverage"]["score"] == 15.0
    assert rubric["D_ai_leverage"]["max"] == 15
    assert rubric["E_verification"]["score"] == 15.0
    assert rubric["E_verification"]["max"] == 15
    assert rubric["F_communication"]["score"] == 10.0
    assert rubric["F_communication"]["max"] == 10
    assert rubric["G_recovery"]["score"] == 10.0
    assert rubric["G_recovery"]["max"] == 10
    assert scored["total_score"] == 98.0
    assert scored["metrics"]["steps"]["opened"] == 1
    assert scored["metrics"]["steps"]["total"] == 3
    blob = str(scored).lower()
    assert "gpt" not in blob
    assert "claude" not in blob


def test_blind_accept_without_a_later_test_hurts_leverage_and_verification():
    events = [
        {"event_type": "file_viewed", "payload": {"path": "src/statusMachine.ts"}},
        {
            "event_type": "ai_edit_accepted",
            "payload": {"path": "src/statusMachine.ts", "base_revision": 1},
        },
        {
            "event_type": "file_changed",
            "payload": {"path": "src/statusMachine.ts", "bytes": 80, "source": "ai"},
        },
    ]
    scored = score_session_v2(
        events=events,
        test_summary={"ok": False},
        challenge_slug="invoice-status-transition",
    )
    assert scored["rubric"]["A_correctness"]["score"] == 0.0
    assert scored["rubric"]["D_ai_leverage"]["score"] == 0.0
    assert scored["rubric"]["E_verification"]["score"] == 0.0
    assert scored["rubric"]["G_recovery"]["score"] == 0.0


def test_irrelevant_diff_lowers_fix_quality_and_a_revert_helps():
    events = [
        {"event_type": "file_viewed", "payload": {"path": "src/statusMachine.ts"}},
        {
            "event_type": "file_changed",
            "payload": {"path": "src/timezoneFormat.ts", "bytes": 90, "source": "ai"},
        },
        {"event_type": "change_reverted", "payload": {"path": "src/timezoneFormat.ts"}},
        {"event_type": "test_result", "payload": {"ok": False}},
        {
            "event_type": "file_changed",
            "payload": {"path": "src/statusMachine.ts", "bytes": 20, "source": "candidate"},
        },
        {"event_type": "test_result", "payload": {"ok": True}},
    ]
    scored = score_session_v2(
        events=events,
        test_summary={"ok": True},
        challenge_slug="invoice-status-transition",
    )
    assert scored["rubric"]["C_fix_quality"]["score"] == 4.0
    assert scored["rubric"]["G_recovery"]["score"] == 10.0


def test_previous_attempt_matches_task_and_scoring_version_only():
    rows = [
        {
            "status": "submitted",
            "scoring_version": "v1",
            "total_score": 40,
            "rubric": {"A_correctness": {"score": 8, "max": 25}},
            "steps": {"opened": 1, "total": 3},
        },
        {
            "status": "submitted",
            "scoring_version": "v2",
            "total_score": 70,
            "rubric": {"A_correctness": {"score": 25, "max": 25}},
            "steps": {"opened": 2, "total": 3},
        },
    ]
    picked = previous_attempt_for(rows, scoring_version="v2")
    assert picked["total_score"] == 70
    assert picked["steps"]["opened"] == 2
    assert previous_attempt_for(rows[:1], scoring_version="v2") is None


def test_extra_defend_question_uses_an_accepted_path():
    base = [{"question": "What stayed?", "index": 0}]
    out = append_accepted_defend_question(
        base,
        [
            {"event_type": "ai_edit_rejected", "payload": {"path": "src/timezoneFormat.ts"}},
            {"event_type": "ai_edit_accepted", "payload": {"path": "src/statusMachine.ts"}},
            {"event_type": "ai_edit_accepted", "payload": {"path": "src/invoiceService.ts"}},
        ],
    )
    assert len(out) == 2
    assert out[1]["question"] == (
        "Walk through the change you accepted in `src/invoiceService.ts`. "
        "What would a wrong version still pass?"
    )
    assert "answer_guide" not in out[1]
    assert append_accepted_defend_question(base, []) == base


def _build_test_app(tmp_path, monkeypatch):
    from app import main as main_module
    from app.core.config import get_settings
    from app.db import session as session_module

    monkeypatch.setenv("PROMPTCODE_DEBUG", "true")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "test-only-secret-not-used-in-prod")
    monkeypatch.setenv("PROMPTCODE_RUNNER", "local")
    get_settings.cache_clear()

    db_file = tmp_path / "prep_arch.db"
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


def test_stale_accept_is_refused_and_reject_writes_nothing(tmp_path, monkeypatch):
    app, test_engine = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            user = client.post(
                "/api/auth/signup",
                json={
                    "email": "rev@example.com",
                    "username": "revuser",
                    "password": _PASSWORD,
                    "first_name": "Rev",
                    "last_name": "User",
                },
            )
            assert user.status_code == 201, user.text
            headers = {"Authorization": f"Bearer {user.json()['access_token']}"}
            slug = "invoice-status-transition"
            start = client.post(
                "/api/interview/sessions",
                headers=headers,
                json={"challenge_slug": slug},
            )
            assert start.status_code == 200, start.text
            sid = start.json()["id"]
            headers = {**headers, "X-Session-Token": start.json()["owner_token"]}
            path = "src/statusMachine.ts"
            original = client.get(
                f"/api/interview/sessions/{sid}/files/{path}", headers=headers
            )
            assert original.status_code == 200, original.text
            original_text = original.json()["content"]

            saved = client.put(
                f"/api/interview/sessions/{sid}/files/{path}",
                headers=headers,
                json={"content": original_text + "\n// candidate\n"},
            )
            assert saved.status_code == 200, saved.text
            current = saved.json()["content"]

            stale = client.post(
                f"/api/interview/sessions/{sid}/ai/apply",
                headers=headers,
                json={
                    "path": path,
                    "content": original_text + "\n// stale suggestion\n",
                    "disposition": "accepted",
                    "base_revision": 1,
                },
            )
            assert stale.status_code == 409, stale.text
            assert "changed" in stale.text.lower()
            after_stale = client.get(
                f"/api/interview/sessions/{sid}/files/{path}", headers=headers
            )
            assert after_stale.json()["content"] == current

            rejected = client.post(
                f"/api/interview/sessions/{sid}/ai/apply",
                headers=headers,
                json={
                    "path": path,
                    "content": original_text + "\n// should not land\n",
                    "disposition": "rejected",
                },
            )
            assert rejected.status_code == 200, rejected.text
            assert rejected.json()["content"] == current

            accepted = client.post(
                f"/api/interview/sessions/{sid}/ai/apply",
                headers=headers,
                json={
                    "path": path,
                    "content": original_text + "\n// accepted\n",
                    "disposition": "accepted",
                    "base_revision": 2,
                },
            )
            assert accepted.status_code == 200, accepted.text
            assert accepted.json()["content"].endswith("// accepted\n")

            edited = client.post(
                f"/api/interview/sessions/{sid}/ai/apply",
                headers=headers,
                json={
                    "path": path,
                    "content": original_text + "\n// edited by hand\n",
                    "disposition": "modified",
                    "proposed_content": original_text + "\n// model body\n",
                    "base_revision": 3,
                },
            )
            assert edited.status_code == 200, edited.text
            events = client.get(
                f"/api/interview/sessions/{sid}/events", headers=headers
            ).json()
            modified = [e for e in events if e["event_type"] == "ai_edit_modified"]
            assert modified
            assert "model body" in modified[-1]["payload"]["proposed_content"]
            assert "edited by hand" in modified[-1]["payload"]["content"]
            rejected_events = [e for e in events if e["event_type"] == "ai_edit_rejected"]
            assert rejected_events
    finally:
        asyncio.run(test_engine.dispose())
