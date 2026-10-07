"""Pause/recovery, abandonment and retry rules for practice sessions."""
import asyncio
import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import async_sessionmaker
from test_interview_multidevice import _build_test_app, _cleanup, _signup

from app.models.interview_session import InterviewEvaluation, InterviewSession
from app.models.user import User
from app.services.interview import lifecycle


@pytest.fixture
def clock(monkeypatch):
    now = [datetime.now(timezone.utc)]
    monkeypatch.setattr(lifecycle, "utcnow", lambda: now[0])
    return now


def session(clock):
    return InterviewSession(status="active", timer_elapsed_ms=0,
                            expires_at=clock[0] + timedelta(hours=24))


def test_timer_pauses_and_resumes_without_counting_absence(clock):
    attempt = session(clock)
    lifecycle.update_timer(attempt, "resume", "a" * 16)
    clock[0] += timedelta(seconds=12)
    lifecycle.update_timer(attempt, "pause", "a" * 16)
    assert lifecycle.timer_snapshot(attempt) == (12000, 0)
    clock[0] += timedelta(hours=3)
    lifecycle.update_timer(attempt, "resume", "b" * 16)
    clock[0] += timedelta(seconds=4)
    assert lifecycle.timer_snapshot(attempt)[0] == 16000


def test_unclean_disconnect_counts_at_most_one_lease(clock):
    attempt = session(clock)
    lifecycle.update_timer(attempt, "resume", "a" * 16)
    clock[0] += timedelta(hours=2)
    assert lifecycle.timer_snapshot(attempt) == (30000, 0)
    lifecycle.update_timer(attempt, "resume", "b" * 16)
    assert lifecycle.timer_snapshot(attempt)[0] == 30000
    with pytest.raises(HTTPException):
        lifecycle.update_timer(attempt, "pause", "a" * 16)
    assert attempt.timer_editor_token == "b" * 16


@pytest.mark.parametrize("status", ["submitted", "abandoned", "expired", "failed"])
def test_terminal_sessions_cannot_resume_or_mutate(clock, status):
    attempt = session(clock)
    attempt.status = status
    attempt.timer_elapsed_ms = 12345
    assert lifecycle.timer_snapshot(attempt) == (12345, 0)
    with pytest.raises(HTTPException):
        lifecycle.update_timer(attempt, "resume", "a" * 16)
    with pytest.raises(HTTPException):
        lifecycle.require_mutable(attempt)


def test_expiry_freezes_at_deadline(clock):
    attempt = session(clock)
    attempt.expires_at = clock[0] + timedelta(seconds=10)
    lifecycle.update_timer(attempt, "resume", "a" * 16)
    clock[0] += timedelta(seconds=15)
    assert lifecycle.maybe_expire_session(attempt)
    assert attempt.status == "expired"
    assert lifecycle.timer_snapshot(attempt) == (10000, 0)


def test_stale_heartbeat_cannot_restart_timer(clock):
    attempt = session(clock)
    lifecycle.update_timer(attempt, "resume", "a" * 16)
    clock[0] += timedelta(seconds=31)
    with pytest.raises(HTTPException):
        lifecycle.update_timer(attempt, "heartbeat", "a" * 16)
    assert lifecycle.timer_snapshot(attempt) == (30000, 0)


@pytest.fixture
def api(tmp_path, monkeypatch):
    app, engine = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            user = _signup(client, email="timer@example.com", username="timer_user")
            headers = {"Authorization": "Bearer " + user["access_token"]}
            slug = client.get("/api/interview/challenges").json()[0]["slug"]
            yield client, headers, slug
    finally:
        _cleanup(app, engine)


def test_start_retry_abandon_and_fresh_restart(api, clock):
    client, headers, slug = api
    start = lambda: client.post("/api/interview/sessions", headers=headers, json={"challenge_slug": slug})
    first = start().json()
    assert first["elapsed_ms"] == 0 and not first["timer_running"]
    assert start().json()["id"] == first["id"]
    base = "/api/interview/sessions/" + first["id"]
    token = "a" * 16
    resumed = client.post(base + "/timer", headers=headers, json={"action": "resume", "editor_token": token})
    assert resumed.status_code == 200 and resumed.json()["timer_running"]
    owner = {**headers, "X-Editor-Token": token}
    clock[0] += timedelta(seconds=8)
    abandoned = client.post(base + "/abandon", headers=owner, json={})
    assert abandoned.status_code == 200, abandoned.text
    assert client.post(base + "/abandon", headers=owner, json={}).status_code == 200
    old = client.get(base, headers=headers).json()
    assert old["status"] == "abandoned" and old["elapsed_ms"] == 8000
    assert client.post(base + "/timer", headers=owner, json={"action": "resume", "editor_token": token}).json()["status"] == "abandoned"
    assert client.post(base + "/submit", headers=owner, json={}).status_code == 409
    second = start().json()
    assert second["id"] != first["id"] and second["elapsed_ms"] == 0
    assert second["attempt_number"] == first["attempt_number"] + 1
    cards = client.get("/api/interview/challenges/progress", headers=headers).json()
    card = next(item for item in cards if item["slug"] == slug)
    assert card["active_session_id"] == second["id"]


def test_challenge_progress_batches_evaluations_and_preserves_history(tmp_path, monkeypatch):
    app, engine = _build_test_app(tmp_path, monkeypatch)
    try:
        with TestClient(app) as client:
            owner = _signup(client, email="progress@example.com", username="progress_user")
            headers = {"Authorization": "Bearer " + owner["access_token"]}
            slug = client.get("/api/interview/challenges").json()[0]["slug"]

            async def seed():
                factory = async_sessionmaker(engine, expire_on_commit=False)
                async with factory() as db:
                    user = (await db.execute(select(User).where(User.username == "progress_user"))).scalar_one()
                    now = datetime.now(timezone.utc)
                    attempts = [InterviewSession(
                        user_id=user.id, owner_token="test", challenge_slug=slug,
                        status="submitted", workspace_path="/unused",
                        started_at=now - timedelta(days=1, minutes=i),
                    ) for i in range(24)]
                    active = InterviewSession(
                        user_id=user.id, owner_token="test", challenge_slug=slug,
                        status="active", workspace_path="/unused", started_at=now,
                        expires_at=now + timedelta(days=1),
                    )
                    db.add_all([*attempts, active])
                    await db.flush()
                    db.add_all([InterviewEvaluation(session_id=s.id, total_score=99)
                                for s in attempts[:12]])
                    await db.commit()
                    return str(active.id)

            active_id = asyncio.run(seed())
            queries = []

            def record(_conn, _cursor, statement, _parameters, _context, _many):
                if statement.lstrip().upper().startswith("SELECT") and "interview_evaluations" in statement:
                    queries.append(statement)

            event.listen(engine.sync_engine, "before_cursor_execute", record)
            response = client.get("/api/interview/challenges/progress", headers=headers)
            assert response.status_code == 200, response.text
            card = next(item for item in response.json() if item["slug"] == slug)
            assert card["attempt_count"] == 25
            assert card["progress"] == "in_progress"
            assert card["active_session_id"] == card["latest_session_id"] == active_id
            assert card["best_score"] == 0.0
            assert len(queries) == 1
            untouched = next(item for item in response.json() if item["slug"] != slug)
            assert untouched["best_score"] is None
            assert untouched["progress"] == "not_started"
    finally:
        _cleanup(app, engine)


def test_editor_conflicts_and_saved_revision_recovery(api, clock):
    client, headers, slug = api
    sid = client.post("/api/interview/sessions", headers=headers, json={"challenge_slug": slug}).json()["id"]
    base = "/api/interview/sessions/" + sid
    token = "a" * 16
    timer = lambda action, editor: client.post(base + "/timer", headers=headers, json={"action": action, "editor_token": editor})
    assert timer("resume", token).status_code == 200
    assert timer("resume", "b" * 16).status_code == 409
    files = client.get(base + "/files", headers=headers).json()
    path = next(file["path"] for file in files if file["path"].startswith("src/"))
    url = base + "/files/" + path
    original = client.get(url, headers=headers).json()
    content = original["content"] + "\n"
    body = {"content": content, "base_revision": original["revision"]}
    assert client.put(url, headers=headers, json=body).status_code == 409
    owner = {**headers, "X-Editor-Token": token}
    wrote = client.put(url, headers=owner, json=body)
    assert wrote.status_code == 200, wrote.text
    retried = client.put(url, headers=owner, json=body)
    assert retried.status_code == 200 and retried.json()["revision"] == wrote.json()["revision"]
    assert client.put(url, headers=owner, json={**body, "content": content + "stale"}).status_code == 409
    clock[0] += timedelta(seconds=5)
    assert timer("pause", token).json()["elapsed_ms"] == 5000
    clock[0] += timedelta(hours=1)
    assert timer("resume", "b" * 16).json()["elapsed_ms"] == 5000
    recovered = client.get(url, headers=headers).json()
    assert recovered["content"] == content
    assert recovered["revision"] == wrote.json()["revision"]
    assert client.put(url, headers=owner, json={**body, "base_revision": recovered["revision"]}).status_code == 409


def test_submit_retry_is_frozen_and_grading_does_not_restart_timer(api, clock):
    client, headers, slug = api
    sid = client.post("/api/interview/sessions", headers=headers, json={"challenge_slug": slug}).json()["id"]
    base = "/api/interview/sessions/" + sid
    token = "a" * 16
    owner = {**headers, "X-Editor-Token": token}
    assert client.post(base + "/timer", headers=headers, json={"action": "resume", "editor_token": token}).status_code == 200
    clock[0] += timedelta(seconds=7)
    first = client.post(base + "/submit", headers=owner, json={})
    assert first.status_code == 200, first.text
    clock[0] += timedelta(hours=1)
    assert client.post(base + "/submit", headers=owner, json={}).status_code == 200
    got = client.get(base, headers=headers).json()
    assert got["status"] == "submitted" and got["elapsed_ms"] == 7000
    assert not got["timer_running"]
    assert client.post(base + "/abandon", headers=owner, json={}).status_code == 400
    assert client.post(base + "/timer", headers=owner, json={"action": "heartbeat", "editor_token": token}).json()["elapsed_ms"] == 7000


def test_timer_migration_preserves_historical_duration():
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    path = Path(__file__).parents[1] / "alembic/versions/session02_pause_timer.py"
    spec = importlib.util.spec_from_file_location("timer_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    engine = sa.create_engine("sqlite://")
    with engine.begin() as conn:
        conn.execute(sa.text("CREATE TABLE interview_sessions (id INTEGER PRIMARY KEY, active_duration_ms INTEGER, started_at DATETIME, submitted_at DATETIME, expires_at DATETIME)"))
        conn.execute(sa.text("INSERT INTO interview_sessions (id, active_duration_ms) VALUES (1, 12345), (2, NULL)"))
        conn.execute(sa.text("INSERT INTO interview_sessions (id, started_at) VALUES (3, datetime('now', '-1 minute'))"))
        with Operations.context(MigrationContext.configure(conn)):
            migration.upgrade()
            values = conn.execute(sa.text("SELECT timer_elapsed_ms FROM interview_sessions ORDER BY id")).scalars().all()
            assert values[:2] == [12345, 0]
            assert 59000 <= values[2] <= 61000
            migration.downgrade()
        assert "timer_elapsed_ms" not in {c["name"] for c in sa.inspect(conn).get_columns("interview_sessions")}
    engine.dispose()
