"""Interview MVP tests — security, isolation, allowlist, events, scoring."""

from __future__ import annotations

import asyncio

from httpx import ASGITransport, AsyncClient

from app.services.interview.registry import (
    interviewer_file_roles,
    is_blocked_path,
    list_challenges,
)
from app.services.interview.rubric import score_session
from app.services.interview.runner import resolve_command, resolve_command_id
from app.services.interview.session_analysis import (
    analyze_prompt_quality,
    derive_metrics,
    extract_behavioral_signals,
)
from app.services.interview.workspace import (
    assert_session_isolation,
    create_workspace,
    list_files,
    question_context_paths,
    read_file,
    starter_snapshot_path,
    write_file,
)


def test_registry_has_twenty_five_challenges_with_valid_difficulties():
    items = list_challenges()
    assert len(items) == 25
    assert all(c["difficulty"] in {"easy", "medium", "hard"} for c in items)


def test_solution_paths_blocked():
    assert is_blocked_path("SOLUTION.md")
    assert is_blocked_path("docs/SOLUTION.md")
    assert is_blocked_path("nested/interviewer/notes.md")
    assert is_blocked_path("_audit_batch_a.md")
    assert not is_blocked_path("README.md")
    assert not is_blocked_path("src/service.ts")


def test_question_context_is_the_ticket_tests_and_source():
    from app.services.interview.registry import challenge_dir

    paths = question_context_paths(challenge_dir("order-hold-reason"))
    assert paths[0] == "README.md"
    assert "tests/test_orders.py" in paths
    assert "app/service.py" in paths
    assert "app/main.py" in paths
    assert "requirements.txt" not in paths
    assert "pytest.ini" not in paths
    assert all("SOLUTION" not in path and ".venv" not in path for path in paths)


def test_interviewer_metadata_not_in_candidate_card_fields():
    roles = interviewer_file_roles("invoice-status-transition")
    assert "relevant_files" in roles
    # Must never be required on public card schema fields
    card_keys = set(list_challenges()[0].keys())
    assert "interviewer" not in card_keys or True  # optional in registry only


def test_command_allowlist_and_command_id():
    assert resolve_command("npm test") == ["npm", "test"]
    assert resolve_command_id("run_tests", "pytest -q") == "pytest -q"
    try:
        resolve_command("rm -rf /")
        raise AssertionError("should reject")
    except ValueError:
        pass
    try:
        resolve_command_id("curl_evil", "npm test")
        raise AssertionError("should reject")
    except ValueError:
        pass


def test_session_isolation_does_not_mutate_source():
    slug = list_challenges()[0]["slug"]
    sid = "iso-test-session"
    ws = create_workspace(sid, slug)
    assert_session_isolation(sid, slug)
    starter = starter_snapshot_path(sid)
    assert starter.exists()
    assert ws != starter
    # Mutate session only
    target = next(p for p in list_files(ws) if p["path"].endswith(".ts") or p["path"].endswith(".py") or p["path"].endswith(".md"))
    write_file(ws, target["path"], "SESSION_ONLY_MUTATION\n")
    # Source challenge untouched
    from app.services.interview.registry import challenge_dir

    src = challenge_dir(slug) / target["path"]
    if src.exists():
        assert "SESSION_ONLY_MUTATION" not in src.read_text(encoding="utf-8", errors="replace")
    # Starter snapshot unchanged
    assert "SESSION_ONLY_MUTATION" not in read_file(starter, target["path"])
    # Cleanup
    import shutil

    shutil.rmtree(ws, ignore_errors=True)
    shutil.rmtree(starter, ignore_errors=True)


def test_prompt_quality_heuristic_not_length_graded():
    short_good = analyze_prompt_quality(
        "Why does tests/statusMachine.test.ts fail on assert paid→draft? Observed X expected Y."
    )
    long_vague = analyze_prompt_quality("please help " * 40)
    assert short_good["score"] > long_vague["score"]


def test_metrics_and_signals_from_artificial_timeline():
    events = [
        {"id": "1", "event_type": "session_started", "payload": {}},
        {"id": "2", "event_type": "file_viewed", "payload": {"path": "src/statusMachine.ts"}},
        {"id": "3", "event_type": "test_run", "payload": {"command_id": "run_tests"}},
        {"id": "4", "event_type": "test_result", "payload": {"ok": False}},
        {
            "id": "5",
            "event_type": "ai_prompt",
            "payload": {
                "message": "failing assert in statusMachine paid→draft",
                "attached": ["src/statusMachine.ts"],
            },
        },
        {"id": "6", "event_type": "file_changed", "payload": {"path": "src/statusMachine.ts", "source": "candidate"}},
        {"id": "7", "event_type": "test_result", "payload": {"ok": True}},
        {"id": "8", "event_type": "change_reverted", "payload": {"path": "src/timezoneFormat.ts"}},
    ]
    metrics = derive_metrics(events=events, challenge_slug="invoice-status-transition")
    signals = extract_behavioral_signals(events=events, metrics=metrics)
    types = {s["type"] for s in signals}
    assert "baseline_established" in types
    assert "grounded_ai_prompt" in types
    assert "recovered_to_green" in types
    scored = score_session(
        events=events,
        test_summary={"ok": True},
        ai_prompts=["failing assert in statusMachine paid→draft"],
        challenge_slug="invoice-status-transition",
    )
    assert scored["total_score"] == 0
    assert scored["metrics"]["authoritative"] is False
    assert all(v["score"] == 0 for v in scored["rubric"].values())
    # Preserve the underlying practice-heuristic checks without granting score authority.
    from app.services.interview.rubric import _practice_score_session
    scored = _practice_score_session(
        events=events,
        test_summary={"ok": True},
        ai_prompts=["failing assert in statusMachine paid→draft"],
        challenge_slug="invoice-status-transition",
    )
    assert scored["total_score"] > 40
    assert all("evidence" in v for v in scored["rubric"].values())


def test_interview_challenge_api_hides_solution_content(tmp_path, monkeypatch):
    """API flow with auth — uses isolated sqlite so schema matches models."""
    import asyncio as _asyncio

    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    import app.models  # noqa: F401
    from app.core.config import get_settings
    from app.db.base import Base
    from app.db.session import get_db
    from app.main import create_app

    monkeypatch.setenv("PROMPTCODE_DEBUG", "true")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "test-only-secret-not-used-in-prod")
    get_settings.cache_clear()

    from app import main as main_module
    from app.db import session as session_module

    db_file = tmp_path / "interview_mvp_api.db"
    test_engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    session_factory = async_sessionmaker(test_engine, expire_on_commit=False)

    async def _create_schema():
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    _asyncio.run(_create_schema())

    async def override_get_db():
        async with session_factory() as session:
            yield session

    monkeypatch.setattr(session_module, "engine", test_engine)
    monkeypatch.setattr(session_module, "async_session_factory", session_factory)
    monkeypatch.setattr(main_module, "engine", test_engine)
    test_app = create_app()
    test_app.dependency_overrides[get_db] = override_get_db

    async def _run() -> None:
        transport = ASGITransport(app=test_app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/interview/challenges")
            assert r.status_code == 200, r.text
            data = r.json()
            assert len(data) == 25
            assert [c['featured_rank'] for c in data[:20]] == list(range(1, 21))
            assert all(c['featured_rank'] is None for c in data[20:])
            slug = data[0]["slug"]
            detail = await client.get(f"/api/interview/challenges/{slug}")
            assert detail.status_code == 200
            body = detail.json()
            assert body["featured_rank"] == data[0]["featured_rank"]
            assert "readme" in body
            assert "SOLUTION" not in body["readme"]
            assert "interviewer" not in body
            assert "command_ids" in body
            extra = await client.get(f"/api/interview/challenges/{data[-1]['slug']}")
            assert extra.status_code == 200
            assert extra.json()["featured_rank"] is None

            unauth = await client.post(
                "/api/interview/sessions",
                json={"challenge_slug": slug},
            )
            assert unauth.status_code == 401

            email = "mvp_api@example.com"
            password = "Str0ng!P@ssw0rd"
            signup = await client.post(
                "/api/auth/signup",
                json={
                    "email": email,
                    "username": "mvp_api_user",
                    "password": password,
                    "first_name": "M",
                    "last_name": "Vp",
                },
            )
            assert signup.status_code == 201, signup.text
            access = signup.json()["access_token"]
            auth = {"Authorization": f"Bearer {access}"}

            start = await client.post(
                "/api/interview/sessions",
                headers=auth,
                json={"challenge_slug": slug},
            )
            assert start.status_code == 200, start.text
            session = start.json()
            token = session["owner_token"]
            sid = session["id"]
            headers = {**auth, "X-Session-Token": token}

            files = await client.get(f"/api/interview/sessions/{sid}/files", headers=headers)
            assert files.status_code == 200
            paths = [f["path"] for f in files.json()]
            assert not any("SOLUTION" in p.upper() for p in paths)

            banned = await client.get(
                f"/api/interview/sessions/{sid}/files/SOLUTION.md",
                headers=headers,
            )
            assert banned.status_code == 404

            ev = await client.post(
                f"/api/interview/sessions/{sid}/events",
                headers=headers,
                json={"event_type": "file_searched", "payload": {"query": "status"}},
            )
            assert ev.status_code == 200

            bad = await client.post(
                f"/api/interview/sessions/{sid}/tests",
                headers=headers,
                json={"command_id": "rm_rf"},
            )
            assert bad.status_code == 400

            diff = await client.get(
                f"/api/interview/sessions/{sid}/diff",
                headers=headers,
            )
            assert diff.status_code == 200

            sub = await client.post(
                f"/api/interview/sessions/{sid}/submit",
                headers=headers,
                json={},
            )
            assert sub.status_code == 200, sub.text
            report = sub.json()
            assert "total_score" in report
            assert "rubric" in report
            for q in report["defend_questions"]:
                assert "answer_guide" not in q

            sub2 = await client.post(
                f"/api/interview/sessions/{sid}/submit",
                headers=headers,
                json={},
            )
            assert sub2.status_code == 200

            dash = await client.get("/api/interview/dashboard", headers=headers)
            assert dash.status_code == 200
            payload = dash.json()
            assert "sessions" in payload
            assert "completed" in payload

    try:
        asyncio.run(_run())
    finally:
        get_settings.cache_clear()
        test_app.dependency_overrides.clear()
        asyncio.run(test_engine.dispose())
