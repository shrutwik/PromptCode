"""STUBBED / LOCAL failure-mode checks for the managed stack — NOT live verification.

Same substrate as ``tests/test_managed_workflow_integration.py``: the real FastAPI
routes, the real durable grading worker, the real ``SupabaseObjectStore`` code with
only the ``httpx`` transport stubbed, and a fake ``modal`` SDK injected through
``sys.modules``. No Modal account, token, image, sandbox or Supabase project is
involved, so nothing here proves real provider behaviour — only that the
application's own failure handling is correct.

Covered: duplicate grading jobs, a job whose stored object is missing or tampered,
a job whose object key does not belong to its session, cancellation of a live
sandbox through the real backend singleton, and a sandbox that fails to start
without falling back to host execution.
"""
from __future__ import annotations

import asyncio
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, update

# The stub doubles and fixture live in the workflow integration file; pytest puts
# this file's directory on sys.path, so the sibling module is importable as-is.
from test_managed_workflow_integration import (  # noqa: I001
    _pick_editable_file,
    _run_grading_worker,
    _signup,
    _start_session,
)
from test_managed_workflow_integration import (
    managed as managed,
)

from app.models.interview_grading import InterviewGradingJob
from app.models.interview_session import InterviewSession
from app.services.interview import workspace_store

# --- helpers ----------------------------------------------------------------- #


def _submit(client, sid: str, headers: dict) -> dict:
    response = client.post(f"/api/interview/sessions/{sid}/submit", headers=headers, json={})
    assert response.status_code == 200, response.text
    return response.json()


def _job(managed) -> InterviewGradingJob:
    async def load():
        async with managed.factory() as db:
            job = (await db.execute(select(InterviewGradingJob))).scalar_one()
            db.expunge(job)
            return job

    return asyncio.run(load())


def _make_available(managed) -> None:
    """Clear the retry backoff so the next drain claims the job immediately."""

    async def run() -> None:
        async with managed.factory() as db:
            await db.execute(update(InterviewGradingJob).values(
                available_at=datetime.now(timezone.utc)))
            await db.commit()

    asyncio.run(run())


def _drain_until_settled(managed, *, attempts: int = 4) -> list[str]:
    """Drain the queue, clearing backoff between attempts; return observed statuses."""
    seen: list[str] = []
    for _ in range(attempts):
        _make_available(managed)
        _run_grading_worker()
        seen.append(_job(managed).status)
        if seen[-1] in {"completed", "failed"}:
            break
    return seen


def _start_and_submit(managed, client, slug: str, *, email: str, username: str):
    owner = _signup(client, email=email, username=username)
    session = _start_session(client, slug, owner["access_token"])
    sid, headers = session["id"], session["headers"]
    path = _pick_editable_file(client, sid, headers)
    original = client.get(f"/api/interview/sessions/{sid}/files/{path}", headers=headers)
    assert original.status_code == 200
    saved = client.put(f"/api/interview/sessions/{sid}/files/{path}", headers=headers,
                       json={"content": original.json()["content"] + "\n// managed failure check\n"})
    assert saved.status_code == 200, saved.text
    submitted = _submit(client, sid, headers)
    return sid, headers, path, submitted


def _report_status(client, sid: str, headers: dict) -> str:
    report = client.get(f"/api/interview/sessions/{sid}/report", headers=headers)
    assert report.status_code == 200, report.text
    return report.json()["assessment"]["execution_status"]


@pytest.fixture
def slug(managed) -> str:
    response = managed.client.get("/api/interview/challenges")
    assert response.status_code == 200
    return response.json()[0]["slug"]


# --- duplicate jobs / idempotency -------------------------------------------- #


def test_duplicate_submission_and_grading_job_are_idempotent(managed, slug):
    client = managed.client
    sid, headers, _path, submitted = _start_and_submit(
        managed, client, slug, email="dup@example.com", username="manageddup")
    first_packet = submitted["assessment"]["packet"]

    # Submit is idempotent: the retry returns the same immutable submission and the
    # same durable job instead of freezing a second one.
    again = client.post(f"/api/interview/sessions/{sid}/submit", headers=headers, json={})
    assert again.status_code == 200, again.text
    retry_packet = again.json()["assessment"]["packet"]
    assert retry_packet["source_digest"] == first_packet["source_digest"]
    assert retry_packet["grading_job_id"] == first_packet["grading_job_id"]

    # Re-enqueueing the same immutable submission returns the existing job row.
    digest = first_packet["source_digest"]

    async def reenqueue():
        from types import SimpleNamespace

        from app.workers.interview_grading import enqueue_grading_job

        async with managed.factory() as db:
            session = await db.get(InterviewSession, uuid.UUID(sid))
            same = await enqueue_grading_job(db, session, SimpleNamespace(
                source_digest=digest, source_path=Path("/unused"), manifest=[],
                object_key=f"submitted/{sid}/{digest}"))
            await db.flush()
            same_id = same.id
            conflicted = None
            try:
                await enqueue_grading_job(db, session, SimpleNamespace(
                    source_digest="b" * 64, source_path=Path("/unused"), manifest=[],
                    object_key=f"submitted/{sid}/{'b' * 64}"))
            except ValueError as exc:
                conflicted = str(exc)
            await db.rollback()
            return same_id, conflicted

    same_id, conflicted = asyncio.run(reenqueue())
    assert same_id == uuid.UUID(first_packet["grading_job_id"])
    assert conflicted and "already bound" in conflicted

    # Exactly one job row exists for the session, and grading it once drains the queue.
    async def count_jobs() -> int:
        async with managed.factory() as db:
            return len((await db.execute(select(InterviewGradingJob))).scalars().all())

    assert asyncio.run(count_jobs()) == 1
    assert _drain_until_settled(managed) == ["completed"]
    assert asyncio.run(count_jobs()) == 1
    assert _run_grading_worker() is False, "a completed job must never be graded twice"
    assert _report_status(client, sid, headers) == "completed"


# --- missing / tampered objects ---------------------------------------------- #


def test_missing_stored_object_is_rejected_and_retried_not_graded(managed, slug):
    client = managed.client
    sid, headers, path, submitted = _start_and_submit(
        managed, client, slug, email="missing@example.com", username="managedmissing")
    packet = submitted["assessment"]["packet"]
    digest = packet["source_digest"]
    manifest = packet.get("manifest") or _job(managed).snapshot_manifest["files"]

    # The submission is in the bucket; drop one candidate object.
    file_key = f"submitted/{sid}/{digest}/{path}"
    assert file_key in managed.bucket.objects
    del managed.bucket.objects[file_key]

    with pytest.raises(ValueError, match="integrity"):
        workspace_store.fetch_submission(sid, digest, manifest, Path(managed.workspace_root) / "hydrate")

    statuses = _drain_until_settled(managed)
    job = _job(managed)
    assert statuses[-1] == "failed", statuses
    assert job.attempts == job.max_attempts
    assert job.result is None, "a job whose source cannot be verified must never publish a grade"
    assert job.last_error
    assert _report_status(client, sid, headers) == "failed"


def test_tampered_stored_object_is_rejected_by_digest_verification(managed, slug):
    client = managed.client
    sid, headers, path, submitted = _start_and_submit(
        managed, client, slug, email="tamper@example.com", username="managedtamper")
    packet = submitted["assessment"]["packet"]
    digest = packet["source_digest"]
    manifest = packet.get("manifest") or _job(managed).snapshot_manifest["files"]
    row = next(item for item in manifest if item["path"] == path)

    file_key = f"submitted/{sid}/{digest}/{path}"
    original = managed.bucket.objects[file_key]
    # Same length, different bytes: only the recorded digest can catch this.
    managed.bucket.objects[file_key] = b"x" * len(original)
    assert len(managed.bucket.objects[file_key]) == row["size"]

    with pytest.raises(ValueError, match="integrity"):
        workspace_store.fetch_submission(sid, digest, manifest, Path(managed.workspace_root) / "hydrate")

    statuses = _drain_until_settled(managed)
    job = _job(managed)
    assert statuses[-1] == "failed", statuses
    assert job.result is None
    assert _report_status(client, sid, headers) == "failed"


def test_job_bound_to_another_sessions_object_key_is_refused(managed, slug):
    client = managed.client
    sid, headers, _path, _submitted = _start_and_submit(
        managed, client, slug, email="key@example.com", username="managedkey")

    async def repoint() -> None:
        async with managed.factory() as db:
            await db.execute(update(InterviewGradingJob).values(
                snapshot_key="submitted/" + str(uuid.uuid4()) + "/" + "a" * 64))
            await db.commit()

    asyncio.run(repoint())
    statuses = _drain_until_settled(managed)
    job = _job(managed)
    assert statuses[-1] == "failed", statuses
    assert job.result is None
    assert _report_status(client, sid, headers) == "failed"


# --- cancellation ------------------------------------------------------------- #


def test_cancelling_a_starting_sandbox_terminates_it_and_fails_closed(managed, slug):
    """The abort path must reach the sandbox the route created."""
    from app.services.execution.backend import get_execution_backend

    client = managed.client
    owner = _signup(client, email="cancel@example.com", username="managedcancel")
    session = _start_session(client, slug, owner["access_token"])
    sid, headers = session["id"], session["headers"]

    modal = managed.modal
    modal.block_create = threading.Event()
    modal.create_entered.clear()
    outcome: dict = {}

    def call_route() -> None:
        outcome["response"] = client.post(
            f"/api/interview/sessions/{sid}/tests", headers=headers, json={"command_id": "run_tests"})

    worker = threading.Thread(target=call_route, daemon=True)
    worker.start()
    try:
        assert modal.create_entered.wait(10), "the sandbox was never created"
        # Cancel exactly the way a live abort would: through the shared singleton
        # the dispatcher used.
        get_execution_backend().cancel()
    finally:
        modal.block_create.set()
        worker.join(15)
    modal.block_create = None

    assert not worker.is_alive()
    response = outcome.get("response")
    assert response is not None and response.status_code == 200, outcome
    body = response.json()
    assert body["isolation"] == "modal" and body["runner"] == "modal", body
    assert body["ok"] is False
    assert modal.created, "the sandbox was created before the abort"
    assert all(sandbox.terminated for sandbox in modal.created), (
        "an aborted sandbox must still be terminated"
    )


# --- sandbox failure ---------------------------------------------------------- #


def test_sandbox_start_failure_fails_closed_without_host_fallback(managed, slug):
    client = managed.client
    owner = _signup(client, email="down@example.com", username="manageddown")
    session = _start_session(client, slug, owner["access_token"])
    sid, headers = session["id"], session["headers"]

    managed.modal.create_error = RuntimeError("modal unavailable")
    response = client.post(f"/api/interview/sessions/{sid}/tests",
                           headers=headers, json={"command_id": "run_tests"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "modal_unavailable", body
    assert body["isolation"] == "modal" and body["runner"] == "modal", body
    assert body["stdout"] == ""
    assert "cannot fall back to host" in body["stderr"], body
    assert managed.modal.created == [], "no sandbox should exist after a create failure"


def test_missing_modal_sdk_fails_closed(managed, monkeypatch, slug):
    client = managed.client
    owner = _signup(client, email="nosdk@example.com", username="managednosdk")
    session = _start_session(client, slug, owner["access_token"])
    sid, headers = session["id"], session["headers"]

    # ``None`` in sys.modules makes ``import modal`` raise ImportError.
    monkeypatch.setitem(sys.modules, "modal", None)
    response = client.post(f"/api/interview/sessions/{sid}/tests",
                           headers=headers, json={"command_id": "run_tests"})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["ok"] is False
    assert body["error_code"] == "modal_unavailable", body
    assert body["isolation"] == "modal", body
