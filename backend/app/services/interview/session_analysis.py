"""Derived session metrics, prompt heuristics, and behavioral signals.

Activity volume is never treated as performance by itself — signals require
evidence (events + repo state) and carry explicit confidence.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from app.services.interview.registry import interviewer_file_roles
from app.services.interview.workspace import compute_diff_stats


def analyze_prompt_quality(prompt: str) -> dict[str, Any]:
    """Transparent heuristic — replaceable by a model judge later. Not graded by length."""
    lower = prompt.lower()
    checks = {
        "filename_refs": bool(re.search(r"\b[\w./-]+\.(ts|tsx|js|py|md)\b", prompt)),
        "function_refs": bool(
            re.search(r"\b[a-z_][a-z0-9_]{2,}\s*\(", prompt, re.I)
            or re.search(r"\b(def|function|class)\s+\w+", prompt, re.I)
        ),
        "failing_tests": any(
            k in lower for k in ("fail", "failed", "failing", "assert", "expected")
        ),
        "error_text": any(
            k in lower for k in ("error", "exception", "traceback", "stack", "typeerror")
        ),
        "observed_expected": ("observed" in lower and "expected" in lower)
        or ("actual" in lower and "expected" in lower)
        or ("got" in lower and "want" in lower),
        "constraints": any(
            k in lower
            for k in ("without", "must not", "do not", "constraint", "don't rewrite", "scope")
        ),
        "asks_explanation": any(
            k in lower for k in ("why", "explain", "root cause", "what is wrong")
        ),
        "scope_limit": any(
            k in lower
            for k in ("only this file", "don't change", "minimal", "smallest", "surgical")
        ),
        "new_evidence": any(
            k in lower for k in ("after running", "test output", "i see", "log shows")
        ),
    }
    # Length is not a positive signal; vague short prompts still score low via missing checks.
    hit = sum(1 for v in checks.values() if v)
    score = round(100.0 * hit / max(len(checks), 1), 1)
    if any(k in lower for k in ("fix everything", "rewrite the whole", "entire codebase")):
        score = max(0.0, score - 25)
        checks["overbroad_ask"] = True
    else:
        checks["overbroad_ask"] = False
    return {"score": score, "checks": checks}


def derive_metrics(
    *,
    events: list[dict[str, Any]],
    workspace: Path | None = None,
    challenge_slug: str | None = None,
    starter_root: Path | None = None,
) -> dict[str, Any]:
    by_type: dict[str, list[dict[str, Any]]] = {}
    for e in events:
        by_type.setdefault(e.get("event_type", ""), []).append(e)

    file_views = by_type.get("file_viewed", [])
    file_changes = by_type.get("file_changed", [])
    searches = by_type.get("file_searched", [])
    prompts = by_type.get("ai_prompt", [])
    test_runs = by_type.get("test_run", [])
    test_results = by_type.get("test_result", [])
    reverts = by_type.get("change_reverted", [])
    ai_accepted = by_type.get("ai_edit_accepted", [])
    ai_modified = by_type.get("ai_edit_modified", [])
    ai_rejected = by_type.get("ai_edit_rejected", [])

    viewed_paths = [e.get("payload", {}).get("path") for e in file_views]
    changed_paths = [e.get("payload", {}).get("path") for e in file_changes]

    roles = interviewer_file_roles(challenge_slug) if challenge_slug else {}
    relevant = set(roles.get("relevant_files") or [])
    supporting = set(roles.get("acceptable_supporting") or [])
    irrelevant = set(roles.get("intentionally_irrelevant") or [])

    def _role(path: str | None) -> str:
        if not path:
            return "unknown"
        if path in relevant:
            return "relevant"
        if path in supporting:
            return "supporting"
        if path in irrelevant:
            return "irrelevant"
        # path prefix match
        for r in relevant:
            if path.startswith(r.rstrip("/") + "/") or path == r:
                return "relevant"
        for r in irrelevant:
            if path == r or path.endswith("/" + r.split("/")[-1]):
                return "irrelevant"
        return "other"

    view_roles = [_role(p) for p in viewed_paths if p]
    change_roles = [_role(p) for p in changed_paths if p]
    relevant_exploration = sum(1 for r in view_roles if r in {"relevant", "supporting"})
    unrelated_views = sum(1 for r in view_roles if r == "irrelevant")
    unrelated_churn = sum(1 for r in change_roles if r == "irrelevant")

    prompt_analyses = []
    for e in prompts:
        text = e.get("payload", {}).get("message") or ""
        if not text and isinstance(e.get("payload"), dict):
            # stored as chars only — skip deep analysis
            continue
        prompt_analyses.append(analyze_prompt_quality(text))

    avg_prompt = (
        round(sum(p["score"] for p in prompt_analyses) / len(prompt_analyses), 1)
        if prompt_analyses
        else None
    )

    diff_stats = None
    if workspace is not None and starter_root is not None and starter_root.exists():
        diff_stats = compute_diff_stats(starter_root, workspace)

    first_test_idx = next(
        (i for i, e in enumerate(events) if e.get("event_type") in {"test_run", "test_result"}),
        None,
    )
    first_change_idx = next(
        (i for i, e in enumerate(events) if e.get("event_type") == "file_changed"),
        None,
    )

    return {
        "counts": {
            "file_views": len(file_views),
            "file_changes": len(file_changes),
            "file_searches": len(searches),
            "ai_prompts": len(prompts),
            "test_runs": len(test_runs),
            "test_results": len(test_results),
            "reverts": len(reverts),
            "ai_edits_accepted": len(ai_accepted),
            "ai_edits_modified": len(ai_modified),
            "ai_edits_rejected": len(ai_rejected),
        },
        "exploration": {
            "relevant_views": relevant_exploration,
            "unrelated_file_views": unrelated_views,
            "unrelated_file_churn": unrelated_churn,
            "unique_files_viewed": len({p for p in viewed_paths if p}),
            "unique_files_changed": len({p for p in changed_paths if p}),
        },
        "prompt_quality_avg": avg_prompt,
        "prompt_analyses": prompt_analyses[:20],
        "baseline": {
            "established": first_test_idx is not None,
            "edited_before_baseline": (
                first_change_idx is not None
                and first_test_idx is not None
                and first_change_idx < first_test_idx
            ),
        },
        "diff": diff_stats,
        "note": "Higher activity is not equated with better performance.",
    }


def extract_behavioral_signals(
    *,
    events: list[dict[str, Any]],
    metrics: dict[str, Any],
) -> list[dict[str, Any]]:
    """Evidence-backed signals — not raw metric→score equations."""
    signals: list[dict[str, Any]] = []
    indexed = list(enumerate(events))

    def _ids(*types: str) -> list[str]:
        out = []
        for i, e in indexed:
            if e.get("event_type") in types:
                eid = e.get("id")
                out.append(str(eid) if eid is not None else f"idx:{i}")
        return out[:12]

    baseline = metrics.get("baseline") or {}
    if baseline.get("established"):
        signals.append(
            {
                "type": "baseline_established",
                "strength": "medium",
                "confidence": 0.8,
                "evidence": "At least one test_run/test_result before heavy conclusion.",
                "related_event_ids": _ids("test_run", "test_result"),
                "explanation": "Candidate established a verification baseline during the session.",
            }
        )
    if baseline.get("edited_before_baseline"):
        signals.append(
            {
                "type": "edited_before_baseline",
                "strength": "weak",
                "confidence": 0.7,
                "evidence": "file_changed preceded first test_run.",
                "related_event_ids": _ids("file_changed", "test_run"),
                "explanation": "Edits occurred before an observed test baseline.",
            }
        )

    exploration = metrics.get("exploration") or {}
    if exploration.get("relevant_views", 0) >= 2:
        signals.append(
            {
                "type": "relevant_exploration",
                "strength": "medium",
                "confidence": 0.75,
                "evidence": f"relevant_views={exploration.get('relevant_views')}",
                "related_event_ids": _ids("file_viewed"),
                "explanation": "Opened files marked relevant/supporting for the challenge.",
            }
        )
    if exploration.get("unrelated_file_churn", 0) >= 1:
        signals.append(
            {
                "type": "unrelated_file_churn",
                "strength": "medium",
                "confidence": 0.7,
                "evidence": f"unrelated_churn={exploration.get('unrelated_file_churn')}",
                "related_event_ids": _ids("file_changed"),
                "explanation": "Modified intentionally irrelevant / noise files.",
            }
        )

    prompts = [e for e in events if e.get("event_type") == "ai_prompt"]
    grounded = 0
    for e in prompts:
        payload = e.get("payload") or {}
        attached = payload.get("attached") or payload.get("attached_paths") or []
        msg = (payload.get("message") or "").lower()
        if attached or any(k in msg for k in ("fail", "error", "test", "assert")):
            grounded += 1
    if grounded:
        signals.append(
            {
                "type": "grounded_ai_prompt",
                "strength": "strong" if grounded >= 2 else "medium",
                "confidence": 0.8,
                "evidence": f"grounded_prompts={grounded}/{len(prompts)}",
                "related_event_ids": _ids("ai_prompt"),
                "explanation": "AI prompts referenced attachments, failures, or errors.",
            }
        )
    elif prompts:
        signals.append(
            {
                "type": "ungrounded_ai_prompt",
                "strength": "medium",
                "confidence": 0.65,
                "evidence": f"prompts={len(prompts)} with weak grounding",
                "related_event_ids": _ids("ai_prompt"),
                "explanation": "AI prompts lacked failing-test or file context.",
            }
        )

    if metrics.get("counts", {}).get("reverts", 0):
        signals.append(
            {
                "type": "recovery_via_revert",
                "strength": "medium",
                "confidence": 0.85,
                "evidence": f"reverts={metrics['counts']['reverts']}",
                "related_event_ids": _ids("change_reverted"),
                "explanation": "Candidate reverted a change — adaptive recovery.",
            }
        )

    if metrics.get("counts", {}).get("ai_edits_modified", 0):
        signals.append(
            {
                "type": "ai_edit_critically_reviewed",
                "strength": "strong",
                "confidence": 0.8,
                "evidence": f"modified={metrics['counts']['ai_edits_modified']}",
                "related_event_ids": _ids("ai_edit_modified"),
                "explanation": "Accepted AI suggestion after candidate modification.",
            }
        )

    results = [e for e in events if e.get("event_type") == "test_result"]
    if len(results) >= 2:
        first_ok = bool((results[0].get("payload") or {}).get("ok"))
        last_ok = bool((results[-1].get("payload") or {}).get("ok"))
        if not first_ok and last_ok:
            signals.append(
                {
                    "type": "recovered_to_green",
                    "strength": "strong",
                    "confidence": 0.9,
                    "evidence": "early fail → final pass",
                    "related_event_ids": _ids("test_result"),
                    "explanation": "Tests moved from failing to passing across the session.",
                }
            )

    return signals
