"""Independent human-rating pilot metrics; never validates synthetic fixtures."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from collections import Counter
from pathlib import Path

from app.services.interview.grading import DIMENSIONS, RUBRIC_VERSION
from app.services.interview.registry import list_challenges


def weighted_kappa(pairs: list[tuple[int, int]]) -> float | None:
    """Quadratic weighted Cohen kappa; undefined when chance disagreement is zero."""
    if not pairs:
        return None
    n = len(pairs)
    first, second = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
    observed = sum((a - b) ** 2 / 16 for a, b in pairs) / n
    expected = sum(first[a] * second[b] * (a - b) ** 2 / 16
                   for a in range(5) for b in range(5)) / n ** 2
    return round(1 - observed / expected, 4) if expected else None


def kappa_interval(pairs: list[tuple[int, int]]) -> list[float] | None:
    """Deterministic percentile bootstrap of paired attempts (500 resamples).

    Undefined resamples are excluded; fewer than 80% defined is inconclusive.
    This interval is exploratory, not a guarantee of population validity.
    """
    if len(pairs) < 30:
        return None
    rng = random.Random(1729)
    estimates = [weighted_kappa(rng.choices(pairs, k=len(pairs))) for _ in range(500)]
    values = sorted(value for value in estimates if value is not None)
    if len(values) < 400:
        return None
    return [values[int((len(values) - 1) * .025)], values[int((len(values) - 1) * .975)]]


def calibration_report(records: list[dict], *, challenges: list[str] | None = None,
                       min_attempts: int = 30, audit_evidence: dict | None = None,
                       include_intervals: bool = True) -> dict:
    """Import trusted reviewer exports, not candidate/model-generated scores.

    This validates export structure, not authenticity of imported attestations.
    Operator must source records from authenticated review/evaluator audit logs.
    No outcome-validity or subgroup-fairness claim follows from reviewer agreement.
    """
    if min_attempts < 30:
        raise ValueError("Pilot requires at least 30 independent attempts per challenge")
    challenges = challenges or [c["slug"] for c in list_challenges()]
    valid = {slug: [] for slug in challenges}
    errors = []
    seen = set()
    for index, record in enumerate(records):
        try:
            if not isinstance(record, dict):
                raise ValueError("record must be an object")
            identity = record.get("attempt_id")
            if not identity or identity in seen:
                raise ValueError("missing or duplicate attempt")
            seen.add(identity)
            slug = record.get("challenge_slug")
            if slug not in valid or record.get("rubric_version") != RUBRIC_VERSION:
                raise ValueError("unknown challenge or rubric")
            if record.get("synthetic") is not False or record.get("external_verified") is not True:
                raise ValueError("real attempts with verified external evaluation required")
            if any(not record.get(k) for k in ("snapshot_digest", "packet_digest", "challenge_version",
                                               "evaluator_version", "inventory_digest")):
                raise ValueError("missing evidence bindings")
            reviews = record.get("reviews")
            if not isinstance(reviews, list) or len(reviews) != 2:
                raise ValueError("exactly two independent human reviews required")
            if (any(r.get("reviewer_kind") != "human" or not r.get("reviewer_id") for r in reviews)
                    or reviews[0]["reviewer_id"] == reviews[1]["reviewer_id"]):
                raise ValueError("independent human reviewer identities required")
            applicable = set(DIMENSIONS)
            if record.get("ai_available") is False:
                applicable.remove("D_ai_leverage")
            elif record.get("ai_available") is not True:
                raise ValueError("AI opportunity must be recorded")
            for review in reviews:
                if review.get("packet_digest") != record["packet_digest"]:
                    raise ValueError("review revision mismatch")
                ratings = review.get("ratings") or {}
                if set(ratings) != applicable or any(type(v) is not int or not 0 <= v <= 4
                                                       for v in ratings.values()):
                    raise ValueError("complete applicable integer ratings required")
            valid[slug].append(record)
        except (ValueError, TypeError, KeyError, AttributeError) as exc:
            errors.append({"index": index, "reason": str(exc)})
    results = []
    for slug, attempts in valid.items():
        versions = {(a["challenge_version"], a["evaluator_version"], a["inventory_digest"], a["ai_available"])
                    for a in attempts}
        dimensions = {}
        for dimension in DIMENSIONS:
            pairs = [(a["reviews"][0]["ratings"][dimension], a["reviews"][1]["ratings"][dimension])
                     for a in attempts if dimension in a["reviews"][0]["ratings"]]
            kappa = weighted_kappa(pairs)
            large = sum(abs(a - b) > 1 for a, b in pairs) / len(pairs) if pairs else None
            dimensions[dimension] = {"n": len(pairs), "quadratic_weighted_kappa": kappa,
                "kappa_bootstrap_95_interval": kappa_interval(pairs) if include_intervals else None,
                "interval_status": "offline_bootstrap" if include_intervals else "offline_report_required",
                "agreement_rate": round(sum(a == b for a, b in pairs) / len(pairs), 4) if pairs else None,
                "large_disagreement_rate": round(large, 4) if large is not None else None,
                "confusion": [[sum(a == x and b == y for a, b in pairs) for y in range(5)] for x in range(5)],
                "passes": bool(len(pairs) >= min_attempts and kappa is not None and kappa >= .70
                               and large is not None and large <= .05)}
        # No-AI mode is a separate cohort; do not compare denominators or hide its missingness.
        applicable_metrics = [v for k, v in dimensions.items()
                              if k != "D_ai_leverage" or v["n"] > 0]
        passes = (len(attempts) >= min_attempts and len(versions) == 1
                  and all(m["passes"] for m in applicable_metrics))
        results.append({"challenge_slug": slug, "accepted_attempts": len(attempts),
                        "version_cohorts": len(versions), "dimensions": dimensions,
                        "passes_agreement_gate": passes})
    statistical_pass = bool(not errors and results and all(r["passes_agreement_gate"] for r in results))
    audits = _audit_gates(audit_evidence, valid)
    dataset_digest = hashlib.sha256(json.dumps(records, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return {"rubric_version": RUBRIC_VERSION, "dataset_digest": dataset_digest,
            "records": records, "audit_evidence": audit_evidence, "audit_gates": audits,
            "status": "invalid_data" if errors else "agreement_gate_met" if all(
                r["passes_agreement_gate"] for r in results) else "insufficient_or_disagreeing_data",
            "release_ready": bool(statistical_pass and audits["complete"]), "agreement_gate_met": statistical_pass,
            "invalid_records": errors, "challenges": results,
            "required_other_gates": ["known-good and mutant challenge validation",
                "adversarial evaluator and tenant isolation audit", "independent review authenticity",
                "confidence intervals and measurement review", "accessibility and fairness assessment"],
            "notice": "Agreement alone does not validate hiring decisions. Imported assertions need audit verification."}


REQUIRED_AUDITS = ("challenge_and_mutant_validation", "adversarial_tenant_isolation",
                   "reviewer_authenticity", "measurement_review", "accessibility_and_fairness")


def _audit_gates(audits: dict | None, valid: dict) -> dict:
    """Operator-provided audit references are attestations, never inferred from tests."""
    if not isinstance(audits, dict):
        return {"complete": False, "missing": list(REQUIRED_AUDITS) + ["inventories"]}
    missing = []
    for name in REQUIRED_AUDITS:
        value = audits.get(name)
        if (not isinstance(value, dict) or value.get("completed") is not True
                or not isinstance(value.get("evidence_refs"), list)
                or not value["evidence_refs"] or any(not isinstance(ref, str) or not ref.strip()
                                                  for ref in value["evidence_refs"])):
            missing.append(name)
    inventories = audits.get("inventories")
    if not isinstance(inventories, dict) or set(inventories) != set(valid):
        missing.append("inventories")
    else:
        for slug, attempts in valid.items():
            item = inventories[slug]
            if (not isinstance(item, dict) or not item.get("evidence_ref") or not attempts
                    or any(item.get(key) != attempt[key] for attempt in attempts
                           for key in ("challenge_version", "evaluator_version", "inventory_digest"))):
                missing.append("inventory:" + slug)
    return {"complete": not missing, "missing": missing}


def publication_allowed() -> bool:
    """Default-off. Recompute readiness from a protected operator-owned local file."""
    from app.core.config import get_settings
    settings = get_settings()
    if not settings.grading_publish_reviewed_scores or not settings.grading_calibration_report_path:
        return False
    try:
        path = Path(settings.grading_calibration_report_path)
        if not path.is_file() or path.stat().st_size > 10_000_000:
            return False
        source = json.loads(path.read_text())
        if source.get("rubric_version") != RUBRIC_VERSION or source.get("release_ready") is not True:
            return False
        from app.services.interview.calibration import challenge_version_for
        from app.services.interview.trusted_cases import VERSION, inventory_digest
        inventories = (source.get("audit_evidence") or {}).get("inventories") or {}
        expected_slugs = {c["slug"] for c in list_challenges()}
        if set(inventories) != expected_slugs:
            return False
        for slug in expected_slugs:
            item = inventories[slug]
            if (item.get("challenge_version") != challenge_version_for(slug)
                    or item.get("evaluator_version") != VERSION
                    or item.get("inventory_digest") != inventory_digest(slug)):
                return False
        rebuilt = calibration_report(source["records"], audit_evidence=source.get("audit_evidence"),
                                     include_intervals=False)
        return bool(rebuilt["release_ready"] and rebuilt["dataset_digest"] == source.get("dataset_digest"))
    except (OSError, ValueError, TypeError, KeyError, AttributeError):
        return False


def pilot_template() -> dict:
    return {"rubric_version": RUBRIC_VERSION, "records": [],
            "challenges": [{"slug": c["slug"], "anchor_status": "pending_independent_validation",
                "required_anchors": ["correct", "partial", "incorrect", "polished_but_wrong",
                                     "no_AI", "interrupted", "adversarial"],
                "minimum_real_attempts": 30} for c in list_challenges()]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", nargs="?", help="JSON records exported from trusted review audit logs")
    parser.add_argument("--template", action="store_true")
    parser.add_argument("--output", help="Write JSON report here")
    parser.add_argument("--audit-evidence", help="Protected operator audit references JSON")
    args = parser.parse_args()
    if args.template:
        result = pilot_template()
    elif args.input:
        source = json.loads(Path(args.input).read_text())
        result = calibration_report(source if isinstance(source, list) else source["records"],
                                    audit_evidence=json.loads(Path(args.audit_evidence).read_text())
                                    if args.audit_evidence else None)
    else:
        parser.error("supply input or --template")
    encoded = json.dumps(result, indent=2)
    if args.output:
        Path(args.output).write_text(encoded + "\n")
    else:
        print(encoded)


if __name__ == "__main__":
    main()
