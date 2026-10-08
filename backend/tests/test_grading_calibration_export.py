from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.interview.calibration import challenge_version_for
from app.services.interview.grading import DIMENSIONS, _digest, pending_assessment
from scripts import export_grading_calibration as exporter


class Result:
    def __init__(self, rows): self.rows = rows
    def scalars(self): return self
    def all(self): return self.rows


def fixture(monkeypatch, *, same_reviewer=False):
    owner, identity = uuid4(), uuid4()
    version = challenge_version_for("order-hold-reason")
    session = SimpleNamespace(id=identity, user_id=owner)
    assessment = pending_assessment(session_id=str(identity), challenge_slug="order-hold-reason",
                                    challenge_version=version, events=[], test_summary={})
    assessment["packet"]["evidence"].append({"id": "evaluation:trusted", "kind": "external_evaluation"})
    assessment["packet_digest"] = _digest(assessment["packet"])
    job = SimpleNamespace(challenge_slug="order-hold-reason", challenge_version=version, source_digest="source",
        result={"payload": {"evaluator_version": exporter.VERSION,
                             "inventory_digest": exporter.inventory_digest("order-hold-reason")}})
    first, second = uuid4(), uuid4()
    rows = []
    for index, reviewer in enumerate((first, first if same_reviewer else second)):
        data = {"reviewer_id": str(reviewer), "reviewer_kind": "human", "rubric_version": "v3-evidence",
            "packet_digest": assessment["packet_digest"], "dimensions": {
                key: {"rating": 3, "rationale": "Independent review of evidence for the requirement.",
                      "evidence_ids": ["evaluation:trusted"]} for key in DIMENSIONS if key != "D_ai_leverage"},
            "manual_checks": {}}
        rows.append(SimpleNamespace(reviewer_id=reviewer, review=data, revision=index + 1))
    monkeypatch.setattr(exporter, "review_context", AsyncMock(return_value=(session, job, None, assessment)))
    db = SimpleNamespace(execute=AsyncMock(side_effect=[Result([identity]), Result(rows)]),
                         get=AsyncMock(return_value=SimpleNamespace(role="interviewer")), rollback=AsyncMock())
    return db, job, rows


@pytest.mark.asyncio
async def test_real_pilot_attestation_required_before_db_read():
    db = SimpleNamespace(execute=AsyncMock())
    result = await exporter.export_calibration_records(db)
    assert result["records"] == []
    assert result["status"] == "real_pilot_confirmation_required"
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_export_pairs_verified_distinct_humans_no_private_content(monkeypatch):
    db, job, rows = fixture(monkeypatch)
    result = await exporter.export_calibration_records(db, confirm_real_pilot=True)
    assert len(result["records"]) == 1
    record = result["records"][0]
    assert record["external_verified"] is True
    assert record["synthetic"] is False
    assert record["reviews"][0]["reviewer_id"] != record["reviews"][1]["reviewer_id"]
    assert "source" not in record
    assert "ai_transcript" not in record
    db.rollback.assert_awaited_once()


@pytest.mark.asyncio
async def test_same_reviewer_cannot_count_as_two_independent_ratings(monkeypatch):
    db, _, _ = fixture(monkeypatch, same_reviewer=True)
    result = await exporter.export_calibration_records(db, confirm_real_pilot=True)
    assert result["records"] == []
    assert result["excluded"] == {"two_independent_current_reviews_required": 1}


@pytest.mark.asyncio
async def test_unsigned_or_tampered_execution_not_exported(monkeypatch):
    db, _, _ = fixture(monkeypatch)
    monkeypatch.setattr(exporter, "review_context", AsyncMock(side_effect=HTTPException(409, "bad signature")))
    result = await exporter.export_calibration_records(db, confirm_real_pilot=True)
    assert result["records"] == []
    assert result["excluded"] == {"evidence_not_verified": 1}


@pytest.mark.asyncio
async def test_stale_inventory_not_exported(monkeypatch):
    db, job, _ = fixture(monkeypatch)
    job.result["payload"]["inventory_digest"] = "stale"
    result = await exporter.export_calibration_records(db, confirm_real_pilot=True)
    assert result["records"] == []
    assert result["excluded"] == {"stale_deployed_version": 1}


@pytest.mark.asyncio
async def test_caller_supplied_reviewer_identity_does_not_count(monkeypatch):
    db, _, rows = fixture(monkeypatch)
    rows[1].review["reviewer_id"] = str(uuid4())
    result = await exporter.export_calibration_records(db, confirm_real_pilot=True)
    assert result["records"] == []
