import json
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

from app.services.interview import grading_feedback as feedback
from app.services.interview.grading import pending_assessment


class Result:
    def scalars(self): return self
    def all(self): return []


def setup(monkeypatch, output):
    identity = uuid4()
    session = SimpleNamespace(id=identity, user_id=uuid4(), challenge_slug="order-hold-reason")
    assessment = pending_assessment(session_id=str(identity), challenge_slug=session.challenge_slug,
        challenge_version="1", events=[], test_summary={})
    evaluation = SimpleNamespace(session_id=identity, metrics={"assessment": assessment})
    provider = SimpleNamespace(api_url="https://api.deepseek.com/v1", api_key="secret",
                               model="deepseek-flash", complete=AsyncMock(return_value={"content": json.dumps(output)}))
    monkeypatch.setattr(feedback, "ProductionAIProvider", lambda: provider)
    reserve = AsyncMock()
    monkeypatch.setattr(feedback, "reserve_ai_budget", reserve)
    return SimpleNamespace(execute=AsyncMock(return_value=Result())), session, evaluation, provider, reserve


@pytest.mark.asyncio
async def test_budget_and_single_call_no_scores(monkeypatch):
    db, session, evaluation, provider, reserve = setup(monkeypatch, {"observations": []})
    result = await feedback.generate_grading_feedback(db, session, evaluation)
    assert result["status"] == "suggested_feedback"
    reserve.assert_awaited_once()
    assert reserve.await_args.kwargs == {"output_tokens": 600, "attempts": 1}
    provider.complete.assert_awaited_once()
    assert "total_score" not in result


@pytest.mark.asyncio
async def test_kill_switch_denies_network(monkeypatch):
    db, session, evaluation, provider, reserve = setup(monkeypatch, {"observations": []})
    reserve.side_effect = HTTPException(503, "disabled")
    result = await feedback.generate_grading_feedback(db, session, evaluation)
    assert result["status"] == "pending_review"
    provider.complete.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize("output", [
    {"observations": [], "total_score": 100},
    {"observations": [{"dimension": "A_correctness", "evidence_ids": ["forged"],
                       "observation": "Everything is completely correct", "counterevidence": "none"}]},
])
async def test_model_cannot_mint_ratings_or_evidence(monkeypatch, output):
    db, session, evaluation, provider, reserve = setup(monkeypatch, output)
    result = await feedback.generate_grading_feedback(db, session, evaluation)
    assert result["status"] == "pending_review"
    assert result["observations"] == []


@pytest.mark.asyncio
async def test_stale_revision_or_foreign_owner_denies_call(monkeypatch):
    db, session, evaluation, provider, reserve = setup(monkeypatch, {"observations": []})
    evaluation.metrics["assessment"]["packet"]["session_id"] = str(uuid4())
    result = await feedback.generate_grading_feedback(db, session, evaluation)
    assert result["reason"] == "invalid_evidence_revision"
    reserve.assert_not_awaited()
    provider.complete.assert_not_awaited()


@pytest.mark.asyncio
async def test_missing_key_no_reservation(monkeypatch):
    db, session, evaluation, provider, reserve = setup(monkeypatch, {"observations": []})
    provider.api_key = ""
    result = await feedback.generate_grading_feedback(db, session, evaluation)
    assert result["reason"] == "provider_not_configured"
    reserve.assert_not_awaited()


@pytest.mark.asyncio
async def test_substantive_verified_behavior_included_without_expected_outputs(monkeypatch):
    from app.services.interview.grading import _digest
    db, session, evaluation, provider, reserve = setup(monkeypatch, {"observations": [{
        "dimension": "A_correctness", "evidence_ids": ["evaluation:trusted"],
        "observation": "The signed behavior check failed this requirement.",
        "counterevidence": "Other requirements require human review."}]})
    envelope = {"payload": {"session_id": str(session.id), "source_digest": "source",
        "challenge_slug": session.challenge_slug, "score_percent": 0,
        "cases": [{"id": "reason-persists", "passed": False, "error": None,
                   "weight": 4, "expected": "secret", "probe": "secret code"}],
        "manual_requirements": []}, "signature": "trusted-caller-verified"}
    assessment = evaluation.metrics["assessment"]
    assessment["packet"]["source_digest"] = "source"
    assessment["packet"]["evidence"].append({"id": "evaluation:trusted", "kind": "external_evaluation",
                                          "payload_digest": _digest(envelope)})
    assessment["packet_digest"] = _digest(assessment["packet"])
    result = await feedback.generate_grading_feedback(db, session, evaluation, external_result=envelope)
    assert result["status"] == "suggested_feedback"
    content = provider.complete.await_args.kwargs["messages"][0]["content"]
    assert '"passed": false' in content
    assert "secret" not in content
    assert "reason-persists" in content


@pytest.mark.asyncio
async def test_digest_only_correctness_evidence_cannot_be_cited(monkeypatch):
    from app.services.interview.grading import _digest
    db, session, evaluation, provider, reserve = setup(monkeypatch, {"observations": [{
        "dimension": "A_correctness", "evidence_ids": ["evaluation:trusted"],
        "observation": "This unobserved result looks completely correct.", "counterevidence": "unknown"}]})
    assessment = evaluation.metrics["assessment"]
    assessment["packet"]["evidence"].append({"id": "evaluation:trusted", "kind": "external_evaluation",
                                           "payload_digest": "digest-only"})
    assessment["packet_digest"] = _digest(assessment["packet"])
    result = await feedback.generate_grading_feedback(db, session, evaluation)
    assert result["reason"] == "invalid_model_evidence"
