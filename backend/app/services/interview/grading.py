"""Evidence-bound practice review. No model, client or runner can confer authority.

Reviewer authentication and external-result verification belong to the trusted
caller. This module is not a public review endpoint or a production evaluator.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

RUBRIC_VERSION: Literal["v3-evidence"] = "v3-evidence"
DIMENSIONS = {
    "A_correctness": ("Functional correctness", 35),
    "B_investigation": ("Problem diagnosis", 15),
    "C_fix_quality": ("Implementation quality", 15),
    "D_ai_leverage": ("AI oversight", 10),
    "E_verification": ("Verification", 15),
    "F_communication": ("Explanation and ownership", 10),
}
ANCHORS = {0: "Demonstrated incorrect approach", 1: "Weak", 2: "Partial",
           3: "Meets task requirements", 4: "Strong with additional evidence"}


def _digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def pending_assessment(*, session_id: str, challenge_slug: str,
                       challenge_version: str | None, events: list[dict],
                       test_summary: dict, defend_answers: dict | None = None) -> dict:
    """Record observations, without inferring ability from activity or keywords."""
    evidence = []
    for index, event in enumerate(events):
        payload = event.get("payload") or {}
        evidence.append({
            "id": f"event:{event.get('id') or index}",
            "kind": "session_observation",
            "event_type": str(event.get("event_type") or ""),
            "payload_digest": _digest(payload),
        })
    evidence.append({"id": "execution:submit", "kind": "advisory_execution",
                     "payload_digest": _digest(test_summary)})
    for index, answer in sorted((defend_answers or {}).items()):
        evidence.append({"id": f"defend:{index}", "kind": "candidate_statement",
                         "payload_digest": _digest(answer)})
    # A refused/failed request is not an opportunity to demonstrate AI oversight.
    ai_available = any(
        event.get("event_type") == "ai_response"
        and (event.get("payload") or {}).get("provider") != "guardrail"
        for event in events
    )
    packet = {"session_id": str(session_id), "challenge_slug": challenge_slug,
              "challenge_version": challenge_version, "rubric_version": RUBRIC_VERSION,
              "ai_available": ai_available, "evidence": evidence}
    return {
        "rubric_version": RUBRIC_VERSION, "status": "pending_review",
        "total_score": None, "authoritative": False,
        "notice": "Not assessed. Activity and practice test output do not establish a grade.",
        "packet": packet, "packet_digest": _digest(packet),
        "dimensions": {
            key: {"label": label, "weight": weight, "rating": None,
                  "status": "not_applicable" if key == "D_ai_leverage" and not ai_available
                  else "not_assessed"}
            for key, (label, weight) in DIMENSIONS.items()
        },
        "anchors": ANCHORS,
    }


class DimensionReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    rating: StrictInt = Field(ge=0, le=4)
    rationale: str = Field(min_length=20, max_length=4000)
    evidence_ids: list[str] = Field(min_length=1, max_length=20)


class HumanReview(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reviewer_id: str = Field(min_length=1, max_length=200)
    reviewer_kind: Literal["human"]
    packet_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    rubric_version: Literal["v3-evidence"]
    dimensions: dict[str, DimensionReview]


def revise_defense(assessment: dict, answers: dict) -> dict:
    """Defense changes invalidate reviews without relabelling submit observations."""
    packet = dict(assessment["packet"])
    packet["evidence"] = [e for e in packet["evidence"] if e["kind"] != "candidate_statement"]
    packet["evidence"] += [{"id": f"defend:{index}", "kind": "candidate_statement",
                            "payload_digest": _digest(answer)}
                           for index, answer in sorted(answers.items())]
    return {**assessment, "packet": packet, "packet_digest": _digest(packet),
            "total_score": None, "status": "pending_review"}


def score_reviewed_assessment(assessment: dict, review: HumanReview) -> dict:
    """Internal, advisory only. Never use a candidate-supplied evidence packet.

Trusted callers must verify external_evaluation provenance before adding that
evidence kind. Merely setting a boolean or kind in an HTTP body is insufficient.
"""
    packet = assessment["packet"]
    if (review.rubric_version != packet.get("rubric_version")
            or review.packet_digest != _digest(packet)
            or review.packet_digest != assessment.get("packet_digest")):
        raise ValueError("Review does not match the evidence revision")
    expected = set(DIMENSIONS)
    if not packet.get("ai_available"):
        expected.remove("D_ai_leverage")
    if set(review.dimensions) != expected:
        raise ValueError("Every applicable dimension must be reviewed exactly once")
    evidence = {item["id"]: item for item in packet["evidence"]}
    if len(evidence) != len(packet["evidence"]):
        raise ValueError("Duplicate evidence IDs")
    dimensions = {}
    weighted = 0.0
    denominator = 0
    for key, (label, weight) in DIMENSIONS.items():
        rating = review.dimensions.get(key)
        if rating is None:
            dimensions[key] = {"label": label, "weight": weight,
                               "rating": None, "status": "not_applicable"}
            continue
        ids = rating.evidence_ids
        if len(ids) != len(set(ids)) or any(item not in evidence for item in ids):
            raise ValueError("Review cites unknown or duplicate evidence")
        if key == "A_correctness" and not any(
                evidence[item]["kind"] == "external_evaluation" for item in ids):
            raise ValueError("Correctness requires verified external evaluation evidence")
        dimensions[key] = {"label": label, "weight": weight, "status": "reviewed",
                           **rating.model_dump()}
        weighted += weight * rating.rating / 4
        denominator += weight
    return {"rubric_version": RUBRIC_VERSION, "status": "reviewed_practice",
            "total_score": round(100 * weighted / denominator, 1),
            "applicable_weight": denominator, "authoritative": False,
            "reviewer_id": review.reviewer_id, "packet_digest": review.packet_digest,
            "dimensions": dimensions,
            "notice": "Human-reviewed practice rating; not a validated hiring assessment."}
