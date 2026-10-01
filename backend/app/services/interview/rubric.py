"""Rubric scoring + SOLUTION.md defend-question extraction (post-submit only)."""

from __future__ import annotations

import re
from typing import Any

from app.services.interview.registry import challenge_dir, interviewer_file_roles
from app.services.interview.session_analysis import (
    analyze_prompt_quality,
    derive_metrics,
    extract_behavioral_signals,
)


def _count(events: list[dict[str, Any]], *types: str) -> int:
    wanted = set(types)
    return sum(1 for e in events if e.get("event_type") in wanted)


def _prompt_quality(prompts: list[str]) -> float:
    if not prompts:
        return 40.0
    scores = [analyze_prompt_quality(p)["score"] for p in prompts]
    return sum(scores) / len(scores)


def score_session(
    *,
    events: list[dict[str, Any]],
    test_summary: dict[str, Any],
    ai_prompts: list[str],
    challenge_slug: str | None = None,
    workspace=None,
    starter_root=None,
) -> dict[str, Any]:
    # Normalize events for analysis (string ids ok)
    norm_events = []
    for e in events:
        if hasattr(e, "event_type"):
            norm_events.append(
                {
                    "id": getattr(e, "id", None),
                    "event_type": e.event_type,
                    "payload": getattr(e, "payload", {}) or {},
                }
            )
        else:
            norm_events.append(e)

    metrics_derived = derive_metrics(
        events=norm_events,
        workspace=workspace,
        challenge_slug=challenge_slug,
        starter_root=starter_root,
    )
    signals = extract_behavioral_signals(events=norm_events, metrics=metrics_derived)
    signal_types = {s["type"] for s in signals}

    tests_ok = bool(test_summary.get("ok"))
    test_runs = _count(norm_events, "test_run", "test_result")
    file_views = _count(norm_events, "file_viewed")
    file_changes = _count(norm_events, "file_changed")
    ai_prompts_n = _count(norm_events, "ai_prompt")
    reverts = _count(norm_events, "change_reverted")
    final_diff = _count(norm_events, "final_diff_viewed")
    pq = _prompt_quality(ai_prompts)

    # A Correctness 25 — evaluator tests primary evidence
    a = 25.0 if tests_ok else (8.0 if test_runs else 0.0)
    a_evidence = (
        "Final allowlisted test command passed."
        if tests_ok
        else "Visible tests did not pass at submit (hidden evaluator cases not leaked)."
    )

    # B Investigation 15 — relevant exploration beats raw view count
    relevant_views = metrics_derived.get("exploration", {}).get("relevant_views", 0)
    b = min(15.0, 2.5 * min(relevant_views, 4) + (3.0 if test_runs else 0.0))
    if "relevant_exploration" in signal_types:
        b = min(15.0, b + 2.0)
    if "unrelated_file_churn" in signal_types:
        b = max(0.0, b - 3.0)
    b_evidence = (
        f"Relevant/supporting views={relevant_views}; "
        f"unrelated churn={metrics_derived.get('exploration', {}).get('unrelated_file_churn', 0)}."
    )

    # C Fix quality / restraint 15 — diff breadth + unrelated churn
    diff = metrics_derived.get("diff") or {}
    changed_n = diff.get("file_count") or file_changes
    c = 12.0 if changed_n and changed_n <= 8 else (6.0 if changed_n else 2.0)
    if reverts:
        c = min(15.0, c + 2.0)
    if "unrelated_file_churn" in signal_types:
        c = max(0.0, c - 4.0)
    c_evidence = f"Files changed≈{changed_n}; reverts={reverts}."

    # D AI leverage quality 15 — grounded prompts + critical review of AI edits
    d = round(15.0 * (pq / 100.0), 1)
    if ai_prompts_n == 0:
        d = 7.0
    if "grounded_ai_prompt" in signal_types:
        d = min(15.0, d + 2.0)
    if "ungrounded_ai_prompt" in signal_types:
        d = max(0.0, d - 2.0)
    if "ai_edit_critically_reviewed" in signal_types:
        d = min(15.0, d + 1.5)
    d_evidence = f"Prompt quality avg={round(pq, 1)}; prompts={ai_prompts_n}."

    # E Verification 10
    e = 10.0 if tests_ok and test_runs else (5.0 if test_runs else 1.0)
    if "baseline_established" in signal_types and tests_ok:
        e = min(10.0, e + 0.0)
    if "edited_before_baseline" in signal_types and not tests_ok:
        e = max(0.0, e - 1.0)
    e_evidence = f"test_runs={test_runs}; final_ok={tests_ok}."

    # F Communication / review hygiene 10
    f = 8.0 if final_diff or file_changes else 4.0
    if final_diff:
        f = min(10.0, f + 1.0)
    f_evidence = f"final_diff_viewed={bool(final_diff)}; file_changes={file_changes}."

    # G Recovery / adaptation 10
    g = 4.0
    if "recovery_via_revert" in signal_types or "recovered_to_green" in signal_types:
        g = 9.0
    elif test_runs >= 2 and tests_ok:
        g = 7.0
    elif test_runs >= 2:
        g = 5.0
    g_evidence = "Signals: " + (
        ", ".join(
            sorted(
                signal_types
                & {"recovery_via_revert", "recovered_to_green", "edited_before_baseline"}
            )
        )
        or "none"
    )

    rubric = {
        "A_correctness": {"score": a, "max": 25, "evidence": a_evidence},
        "B_investigation": {"score": round(b, 1), "max": 15, "evidence": b_evidence},
        "C_fix_quality": {
            "score": round(min(15.0, c), 1),
            "max": 15,
            "evidence": c_evidence,
        },
        "D_ai_leverage": {"score": round(d, 1), "max": 15, "evidence": d_evidence},
        "E_verification": {"score": e, "max": 10, "evidence": e_evidence},
        "F_communication": {"score": round(f, 1), "max": 10, "evidence": f_evidence},
        "G_recovery": {"score": round(g, 1), "max": 10, "evidence": g_evidence},
    }
    total = round(sum(v["score"] for v in rubric.values()), 1)

    metrics = {
        "test_runs": test_runs,
        "file_views": file_views,
        "file_changes": file_changes,
        "ai_prompts": ai_prompts_n,
        "reverts": reverts,
        "prompt_quality_avg": round(pq, 1),
        "tests_passed": tests_ok,
        "derived": metrics_derived,
        "signals": signals,
    }
    insights = []
    went_well = []
    improve = []
    recovery = []
    if tests_ok:
        went_well.append("Final correctness: allowlisted tests passed.")
    else:
        improve.append("Final test run did not pass — correctness capped.")
    if "relevant_exploration" in signal_types:
        went_well.append("Explored relevant/supporting files before concluding.")
    if "unrelated_file_churn" in signal_types:
        improve.append("Spent edit effort on intentionally irrelevant files.")
    if ai_prompts_n and pq < 55:
        improve.append("AI prompts were vague; anchor on failing tests and paths.")
    if "grounded_ai_prompt" in signal_types:
        went_well.append("AI prompts showed grounded context.")
    if file_views == 0:
        improve.append("No file_viewed events — investigation trail is thin.")
    if tests_ok and ai_prompts_n == 0:
        insights.append("Solved without AI — leverage score uses the no-AI baseline.")
    if "recovery_via_revert" in signal_types or "recovered_to_green" in signal_types:
        recovery.append("Showed recovery (revert and/or fail→pass).")
    insights.extend(went_well)
    insights.extend(improve)

    return {
        "total_score": total,
        "rubric": rubric,
        "metrics": metrics,
        "insights": insights,
        "went_well": went_well,
        "improve": improve,
        "recovery_moments": recovery,
        "signals": signals,
    }


def _event_type(event: Any) -> str:
    if isinstance(event, dict):
        return str(event.get("event_type") or "")
    return str(getattr(event, "event_type", "") or "")


def _payload(event: Any) -> dict[str, Any]:
    if isinstance(event, dict):
        raw = event.get("payload") or {}
    else:
        raw = getattr(event, "payload", None) or {}
    return raw if isinstance(raw, dict) else {}


def _norm_events(events: list[Any]) -> list[dict[str, Any]]:
    return [{"event_type": _event_type(e), "payload": _payload(e)} for e in events]


def _file_role(path: str | None, roles: dict[str, list[str]]) -> str:
    if not path:
        return "unknown"
    relevant = set(roles.get("relevant_files") or [])
    supporting = set(roles.get("acceptable_supporting") or [])
    irrelevant = set(roles.get("intentionally_irrelevant") or [])
    if path in relevant:
        return "relevant"
    if path in irrelevant:
        return "irrelevant"
    for item in relevant:
        if path == item or path.startswith(item.rstrip("/") + "/"):
            return "relevant"
    for item in supporting:
        if path == item or path.startswith(item.rstrip("/") + "/"):
            return "supporting"
    for item in irrelevant:
        if path == item or path.endswith("/" + item.split("/")[-1]):
            return "irrelevant"
    return "other"


def _on_task(path: str, roles: dict[str, list[str]]) -> bool:
    return _file_role(path, roles) in {"relevant", "supporting"}


def _change_size(payload: dict[str, Any]) -> int | None:
    if payload.get("bytes") is not None:
        return int(payload["bytes"])
    if payload.get("additions") is None and payload.get("deletions") is None:
        return None
    return int(payload.get("additions") or 0) + int(payload.get("deletions") or 0)


def steps_summary(events: list[Any], challenge_slug: str | None) -> dict[str, int]:
    from app.services.interview.levels import task_for

    norm = _norm_events(events)
    opened = 1 + sum(1 for e in norm if e["event_type"] == "level_advanced")
    task = task_for(challenge_slug) if challenge_slug else None
    total = len(task["levels"]) if task else opened
    return {"opened": min(opened, total) if total else opened, "total": total}


_KEPT_OR_REJECTED = re.compile(
    r"\b(kept|rejected|reject|accepted|discarded)\b", re.IGNORECASE
)


def communication_points(texts: list[str]) -> tuple[float, str]:
    blob = "\n".join(texts)
    if _KEPT_OR_REJECTED.search(blob):
        return 10.0, "A defend answer or note says what was kept or rejected."
    return 0.0, "No defend answer or note yet says what was kept or rejected."


def _communication_texts(events: list[dict[str, Any]], extra: list[str] | None) -> list[str]:
    texts = list(extra or [])
    for event in events:
        if event["event_type"] != "defend_answer":
            continue
        payload = event["payload"]
        for key in ("answer", "text", "note"):
            if payload.get(key):
                texts.append(str(payload[key]))
    return texts


def apply_communication_score(rubric: dict, texts: list[str]) -> tuple[dict, float]:
    score, evidence = communication_points(texts)
    updated = {
        key: dict(value) if isinstance(value, dict) else value
        for key, value in (rubric or {}).items()
    }
    updated["F_communication"] = {"score": score, "max": 10, "evidence": evidence}
    total = round(
        sum(
            float(value["score"])
            for value in updated.values()
            if isinstance(value, dict) and "score" in value
        ),
        1,
    )
    return updated, total


def score_session_v2(
    *,
    events: list[dict[str, Any]],
    test_summary: dict[str, Any],
    ai_prompts: list[str] | None = None,
    challenge_slug: str | None = None,
    workspace=None,
    starter_root=None,
    communication_texts: list[str] | None = None,
) -> dict[str, Any]:
    """Judgment from events and submit tests. No model grades the session."""
    del ai_prompts  # v2 does not grade prompt text with a model or a prompt rubric.
    norm = _norm_events(events)
    roles = interviewer_file_roles(challenge_slug) if challenge_slug else {}
    metrics_derived = derive_metrics(
        events=norm,
        workspace=workspace,
        challenge_slug=challenge_slug,
        starter_root=starter_root,
    )
    signals = extract_behavioral_signals(events=norm, metrics=metrics_derived)

    tests_ok = bool(test_summary.get("ok"))
    a = 25.0 if tests_ok else 0.0
    a_evidence = "Submit tests passed." if tests_ok else "Submit tests did not pass."

    edit_types = {"file_changed", "ai_edit_accepted", "ai_edit_modified"}
    first_edit = next((i for i, e in enumerate(norm) if e["event_type"] in edit_types), None)
    viewed_before = []
    for i, event in enumerate(norm):
        if first_edit is not None and i >= first_edit:
            break
        if event["event_type"] == "file_viewed":
            viewed_before.append(event["payload"].get("path"))
    investigated = any(_file_role(path, roles) == "relevant" for path in viewed_before)
    b = 15.0 if investigated else 0.0
    b_evidence = (
        "Relevant files were opened before the first edit."
        if investigated
        else "Relevant files were not opened before the first edit."
    )

    changed = [
        event["payload"].get("path")
        for event in norm
        if event["event_type"] == "file_changed" and event["payload"].get("path")
    ]
    reverted = any(event["event_type"] == "change_reverted" for event in norm)
    if not changed:
        c = 0.0
        c_evidence = "No file changes."
    elif all(_on_task(path, roles) for path in changed):
        c = 8.0
        c_evidence = "The diff stays on this task's files."
    else:
        c = 2.0
        c_evidence = "The diff leaves this task's files."
    if reverted:
        c = min(10.0, c + 2.0)
        c_evidence = c_evidence + " A revert brought the score up."

    helped = any(event["event_type"] in {"ai_edit_modified", "ai_edit_rejected"} for event in norm)
    blind = False
    for i, event in enumerate(norm):
        if event["event_type"] != "ai_edit_accepted":
            continue
        window = []
        for nxt in norm[i + 1 :]:
            if nxt["event_type"] == "level_advanced":
                break
            window.append(nxt)
        if not any(item["event_type"] in {"test_run", "test_result"} for item in window):
            blind = True
    d = 15.0 if helped else 8.0
    if blind:
        d = max(0.0, d - 8.0)
    if blind:
        d_evidence = "An accept had no later test on that step."
    elif helped:
        d_evidence = "A suggestion was edited or rejected."
    else:
        d_evidence = "No suggestion was edited or rejected."

    act_indexes = [
        i
        for i, event in enumerate(norm)
        if event["event_type"] in {"ai_edit_accepted", "ai_edit_modified"}
    ]
    if not act_indexes:
        ran = any(event["event_type"] in {"test_run", "test_result"} for event in norm)
        e = 15.0 if ran else 0.0
        e_evidence = (
            "Tests ran. There was no accept to verify."
            if ran
            else "No test run."
        )
    else:
        verified = 0
        for n, index in enumerate(act_indexes):
            end = act_indexes[n + 1] if n + 1 < len(act_indexes) else len(norm)
            window = []
            for nxt in norm[index + 1 : end]:
                if nxt["event_type"] == "level_advanced":
                    break
                window.append(nxt)
            if any(item["event_type"] in {"test_run", "test_result"} for item in window):
                verified += 1
        e = round(15.0 * verified / len(act_indexes), 1)
        e_evidence = f"Test after accept on {verified} of {len(act_indexes)}."

    f, f_evidence = communication_points(_communication_texts(norm, communication_texts))

    g = 0.0
    phase = 0
    last_size: int | None = None
    for event in norm:
        if event["event_type"] == "file_changed":
            size = _change_size(event["payload"])
            if (
                phase == 1
                and size is not None
                and last_size is not None
                and size < last_size
            ):
                phase = 2
            if size is not None:
                last_size = size
        elif event["event_type"] == "change_reverted" and phase == 1:
            phase = 2
        elif event["event_type"] in {"test_result", "test_run"} and "ok" in event["payload"]:
            if event["payload"].get("ok") is True and phase == 2:
                g = 10.0
                break
            if event["payload"].get("ok") is False:
                phase = 1
    g_evidence = (
        "A failing test was followed by a smaller fix and a pass."
        if g
        else "No failing test, then a smaller fix, then a pass."
    )

    rubric = {
        "A_correctness": {"score": a, "max": 25, "evidence": a_evidence},
        "B_investigation": {"score": b, "max": 15, "evidence": b_evidence},
        "C_fix_quality": {"score": c, "max": 10, "evidence": c_evidence},
        "D_ai_leverage": {"score": d, "max": 15, "evidence": d_evidence},
        "E_verification": {"score": e, "max": 15, "evidence": e_evidence},
        "F_communication": {"score": f, "max": 10, "evidence": f_evidence},
        "G_recovery": {"score": g, "max": 10, "evidence": g_evidence},
    }
    total = round(sum(item["score"] for item in rubric.values()), 1)
    steps = steps_summary(norm, challenge_slug)
    went_well = []
    improve = []
    recovery = []
    if tests_ok:
        went_well.append("Submit tests passed.")
    else:
        improve.append("Submit tests did not pass.")
    if investigated:
        went_well.append("Opened the relevant files before the first edit.")
    else:
        improve.append("Relevant files were not opened before the first edit.")
    if helped:
        went_well.append("Edited or rejected a suggestion.")
    if blind:
        improve.append("Accepted a suggestion with no later test on that step.")
    if g:
        recovery.append("A failing test was followed by a smaller fix and a pass.")
    insights = went_well + improve + recovery
    return {
        "total_score": total,
        "rubric": rubric,
        "metrics": {
            "steps": steps,
            "tests_passed": tests_ok,
            "derived": metrics_derived,
            "signals": signals,
            "test_runs": sum(1 for event in norm if event["event_type"] in {"test_run", "test_result"}),
            "file_changes": len(changed),
        },
        "insights": insights,
        "went_well": went_well,
        "improve": improve,
        "recovery_moments": recovery,
        "signals": signals,
    }


def previous_attempt_for(
    attempts: list[dict[str, Any]], *, scoring_version: str
) -> dict[str, Any] | None:
    """Earlier submits for the same person and task, newest first."""
    for row in attempts:
        status = row.get("status")
        if status and status != "submitted":
            continue
        if row.get("scoring_version") != scoring_version:
            continue
        return {
            "total_score": row.get("total_score"),
            "rubric": row.get("rubric") or {},
            "steps": row.get("steps"),
            "scoring_version": scoring_version,
        }
    return None


def parse_defend_questions(slug: str) -> list[dict[str, str]]:
    """Server-side only — never call from candidate file APIs."""
    path = challenge_dir(slug) / "SOLUTION.md"
    if not path.exists():
        return _default_defend()
    text = path.read_text(encoding="utf-8")
    m = re.search(
        r"##\s+Defend[- ]Your[- ]Code.*?\n(.*?)(?=\n##\s|\Z)",
        text,
        re.I | re.S,
    )
    section = m.group(1) if m else text
    questions: list[dict[str, str]] = []
    blocks = re.split(r"\n(?=(?:\*\*)?(?:Q\d+|\d+\.)\b)", section)
    for block in blocks:
        block = block.strip()
        if not block or len(block) < 20:
            continue
        lines = block.splitlines()
        q = lines[0].strip().lstrip("*").strip()
        guide = "\n".join(lines[1:]).strip()
        # Many SOLUTION.md rows are "N. Q: …? A: …" on one line — split inline guides.
        inline = re.split(r"\s+A:\s+", q, maxsplit=1)
        if len(inline) == 2:
            q = inline[0].strip()
            if not guide:
                guide = inline[1].strip()
        if "?" in q or q.lower().startswith("q") or re.match(r"\d+\.", q):
            questions.append({"question": q[:500], "answer_guide": guide[:2000]})
        if len(questions) >= 4:
            break
    while len(questions) < 4:
        questions.extend(_default_defend()[len(questions) :])
        break
    return questions[:4]


def sanitize_candidate_question(question: str) -> str:
    """Strip any residual inline answer keys before exposing to candidates."""
    text = re.split(r"\s+A:\s+", (question or "").strip(), maxsplit=1)[0].strip()
    return text[:500]


def candidate_defend_questions(slug: str) -> list[dict[str, str]]:
    """Questions only — strip answer guides for candidate UI."""
    return [
        {"question": sanitize_candidate_question(q["question"]), "index": i}
        for i, q in enumerate(parse_defend_questions(slug))
    ]


_ACCEPTED_DEFEND = (
    "Walk through the change you accepted in `{path}`. "
    "What would a wrong version still pass?"
)


def append_accepted_defend_question(
    questions: list[dict[str, str]], events: list[Any]
) -> list[dict[str, str]]:
    """At most one extra question, from the last file they accepted."""
    path = None
    for event in _norm_events(events):
        if event["event_type"] == "ai_edit_accepted" and event["payload"].get("path"):
            path = event["payload"]["path"]
    if not path:
        return questions
    out = list(questions)
    out.append({"question": _ACCEPTED_DEFEND.format(path=path), "index": len(out)})
    return out


def _default_defend() -> list[dict[str, str]]:
    return [
        {
            "question": "What was the root cause, in one sentence?",
            "answer_guide": "Name the precise behavioral bug, not a vague rewrite.",
        },
        {
            "question": "Which test or reproduction proved the fix?",
            "answer_guide": "Cite the failing assertion and why it now passes.",
        },
        {
            "question": "What incorrect fix did you consider and reject?",
            "answer_guide": "Show awareness of wrong alternatives / AI traps.",
        },
        {
            "question": "What risk remains after your change?",
            "answer_guide": "Edge cases, perf, authz, or ordering caveats.",
        },
    ]
