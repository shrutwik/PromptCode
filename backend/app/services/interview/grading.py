"""Evidence-bound practice review. No model, client or runner can confer authority.

Reviewer authentication and external-result verification belong to the trusted
caller. This module is not a public review endpoint or a production evaluator.
"""
from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, StrictInt

RUBRIC_VERSION: Literal["v4-research-pilot"] = "v4-research-pilot"
DIMENSIONS = {
    "A_correctness": ("Functional correctness", 30),
    "B_investigation": ("Problem framing and codebase investigation", 15),
    "C_fix_quality": ("Implementation quality", 15),
    "D_ai_leverage": ("AI judgment and oversight", 10),
    "E_verification": ("Verification and regression protection", 20),
    "F_communication": ("Explanation and ownership", 10),
}
ANCHORS = {0: "Demonstrated incorrect approach", 1: "Weak", 2: "Partial",
           3: "Meets task requirements", 4: "Strong with additional evidence"}


# Criterion-specific behavioral anchors, shared by candidate and reviewer views.
DIMENSION_ANCHORS = {'A_correctness': {0: 'Demonstrably breaks the core contract or cannot produce the required '
                      'central behavior.',
                   1: 'Some happy-path behavior works, but major required branches or invariants '
                      'fail.',
                   2: 'Most central behavior works; a material required edge case or regression '
                      'remains.',
                   3: 'Meets the stated acceptance behavior, including relevant edge cases and '
                      'preserved behavior, supported by independent evaluation.',
                   4: 'Meets the contract with additional evidence resolving a relevant subtle '
                      'invariant or boundary beyond the minimum demonstration; no unrequested '
                      'features needed.'},
 'B_investigation': {0: 'Misstates the central requirement or changes an unrelated component '
                        'without locating the relevant behavior.',
                     1: 'Guesses from symptoms; overlooks the main state, scope or boundary and '
                        'cannot explain the chosen edit location.',
                     2: 'Finds relevant code and some constraints, but misses an important '
                        'dependency, assumption or root cause.',
                     3: 'Establishes the contract, relevant code path/state model and cause; '
                        'decomposes work into sensible steps.',
                     4: 'Efficiently identifies a non-obvious interaction, resolves consequential '
                        'ambiguity and uses evidence to narrow the solution without unnecessary '
                        'exploration.'},
 'C_fix_quality': {0: 'Introduces a severe unsafe behavior, corrupting design or unusable '
                      'integration.',
                   1: 'Brittle patch, broad unrelated edits or major failure-handling/complexity '
                      'problems.',
                   2: 'Workable approach with material maintainability, boundary-handling or '
                      'integration weaknesses.',
                   3: 'Focused change fitting existing patterns; appropriate data structures, '
                      'failure handling and complexity for stated requirements.',
                   4: 'Clearly resolves a subtle design risk with a simple maintainable '
                      'implementation and explicit tradeoffs; avoids speculative abstractions.'},
 'D_ai_leverage': {0: 'Accepts clearly wrong or unsafe output without checking and cannot justify '
                      'the resulting action despite available evidence.',
                   1: 'Repeatedly delegates without relevant context or review; obvious errors '
                      'persist.',
                   2: 'Supplies useful context and inspects some output, but consequential '
                      'assumptions or integration errors remain unchecked.',
                   3: 'Chooses useful bounded assistance, gives relevant context, reviews '
                      'consequential output and corrects or rejects errors; retains control of the '
                      'work.',
                   4: 'Adapts delegation strategically, independently validates a subtle AI '
                      'assumption and chooses direct action or another tool when it is more '
                      'effective.'},
 'E_verification': {0: 'Claims success despite observed contradictory evidence or actively weakens '
                       'checks to hide failure.',
                    1: 'No meaningful check beyond superficial execution, despite a functioning '
                       'environment and opportunity.',
                    2: 'Checks the main example but misses a material invariant, failure path or '
                       'regression; expectations are weak.',
                    3: 'Runs meaningful checks with justified expectations covering central '
                       'behavior, a relevant edge/failure case and preservation.',
                    4: 'Uses a discriminating counterexample, independent oracle, property or '
                       'plausible-wrong-fix check that reveals a subtle defect; verifies the '
                       'repair and relevant regressions.'},
 'F_communication': {0: 'Cannot explain the central behavior or gives an account contradicted by '
                        'their artifact.',
                     1: 'Describes surface changes but cannot explain why the solution works or '
                        'its main failure mode.',
                     2: 'Understands the main implementation but struggles with an important '
                        'limitation or a small relevant adaptation.',
                     3: 'Accurately explains the change, evidence and limitations; can reason '
                        'through a short relevant counterfactual.',
                     4: 'Gives a precise causal explanation and adapts reasoning to a meaningful '
                        'new constraint, including which assumptions and checks must change.'}}


def public_rubric() -> dict:
    """Public criteria only; never include evaluator fixtures or answer guides."""
    return {"version": RUBRIC_VERSION, "status": "research_informed_pilot",
            "notice": "Human-reviewed practice rubric; not a validated hiring assessment. "
                      "Test results are separate. Optional discussion is ungraded. "
                      "Prompt count, model brand and verbosity do not earn points.",
            "dimensions": {key: {"label": label, "weight": weight,
                                 "anchors": DIMENSION_ANCHORS[key]}
                           for key, (label, weight) in DIMENSIONS.items()}}


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
    ai_context = {
        "permitted": True, "required": False,
        "prompt_observed": any(e.get("event_type") == "ai_prompt" for e in events),
        "response_observed": ai_available,
        # Logs establish observed interaction, not availability throughout a session.
        "availability": "observed" if ai_available else "unknown",
        "assessment_mode": "ai_observed" if ai_available else "ai_not_observed",
    }
    packet = {"session_id": str(session_id), "challenge_slug": challenge_slug,
              "challenge_version": challenge_version, "rubric_version": RUBRIC_VERSION,
              "ai_available": ai_available, "ai_context": ai_context, "evidence": evidence}
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
        "anchors": ANCHORS, "dimension_anchors": DIMENSION_ANCHORS,
        "ai_context": ai_context,
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
    rubric_version: Literal["v4-research-pilot"]
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
    if (packet.get("rubric_version") != RUBRIC_VERSION
            or review.rubric_version != packet.get("rubric_version")
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
            "dimensions": dimensions, "dimension_anchors": DIMENSION_ANCHORS,
            "ai_context": packet.get("ai_context", {}),
            "comparison_notice": (
                "AI judgment was not observed. The adjusted total excludes that dimension "
                "and does not establish equivalent AI competence."
                if not packet.get("ai_available") else None),
            "notice": "Human-reviewed practice rating; not a validated hiring assessment."}
