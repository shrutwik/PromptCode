"""Durable, leased AI grading of immutable submissions and completed defense answers."""
from __future__ import annotations

import asyncio
import copy
import json
import secrets
import time

from sqlalchemy import select

from app.core.config import get_settings
from app.db.session import async_session_factory
from app.models.interview_grading import InterviewGradingJob
from app.models.interview_session import (
    InterviewAIMessage,
    InterviewEvaluation,
    InterviewSession,
    InterviewSessionEvent,
)
from app.services.interview.automated_grading import (
    PROMPT_VERSION,
    aggregate_judgments,
    judge_once,
)
from app.services.interview.grading import RUBRIC_VERSION, _digest
from app.services.interview.grading_review import _review_source, review_context
from app.services.interview.question_parts import review_guidance_for
from app.services.interview.registry import candidate_readme

LEASE_SECONDS = 360
MAX_ATTEMPTS = 2


def defense_complete(evaluation) -> bool:
    answers = (evaluation.metrics or {}).get("defend_answers") or {}
    questions = evaluation.defend_questions or []
    return bool(questions) and all(str(answers.get(str(i), "")).strip() for i in range(len(questions)))


def queue_state(evaluation) -> dict:
    return {"status": "queued" if defense_complete(evaluation) else "waiting_defense",
            "attempts": 0, "prompt_version": PROMPT_VERSION}


async def _bundle(db, session, job, evaluation, assessment) -> dict:
    source = await asyncio.to_thread(_review_source, job, include_content=True)
    evidence = [{"id": "source:" + f["path"], "kind": "submitted_source", "content": f["content"]}
                for f in source if not f["path"].endswith((".lock", "package-lock.json", "yarn.lock"))]
    answers = (evaluation.metrics or {}).get("defend_answers") or {}
    for index, answer in sorted(answers.items()):
        evidence.append({"id": "defend:" + index, "kind": "candidate_statement", "content": str(answer)})
    known = {e["id"]: e for e in assessment["packet"]["evidence"]}
    rows = (await db.execute(select(InterviewSessionEvent).where(
        InterviewSessionEvent.session_id == session.id).order_by(InterviewSessionEvent.created_at).limit(1001))).scalars().all()
    if len(rows) > 1000:
        raise ValueError("Evidence exceeds bounded event context")
    for row in rows:
        identity = f"event:{row.id}"
        if (identity in known and known[identity].get("payload_digest") == _digest(row.payload)
                and row.event_type in {"file_changed", "test_result", "file_viewed", "ai_prompt",
                                       "ai_edit_accepted", "ai_edit_modified", "ai_edit_rejected", "ai_provider_error"}):
            evidence.append({"id": identity, "kind": "session_observation",
                             "content": json.dumps({"event_type": row.event_type, "payload": row.payload}, default=str)})
    if assessment["packet"].get("ai_available"):
        messages = (await db.execute(select(InterviewAIMessage).where(
            InterviewAIMessage.session_id == session.id).order_by(InterviewAIMessage.created_at))).scalars().all()
        for message in messages:
            evidence.append({"id": f"ai:{message.id}", "kind": "ai_interaction",
                             "content": json.dumps({"role": message.role, "content": message.content})})
    payload = job.result["payload"]
    # The judge receives verified outcomes, never test code, inputs or expected answers.
    outcome = {"score_percent": payload["score_percent"],
               "passed_checks": sum(c["passed"] for c in payload["cases"]),
               "total_checks": len(payload["cases"]),
               "manual_requirements": payload.get("manual_requirements", [])}
    evidence.append({"id": "evaluation:trusted", "kind": "external_evaluation", "content": json.dumps(outcome)})
    return {"task": candidate_readme(session.challenge_slug), "guidance": review_guidance_for(session.challenge_slug),
            "behavior_percent": payload["score_percent"], "manual_requirements": outcome["manual_requirements"],
            "ai_observed": bool(assessment["packet"].get("ai_available")), "evidence": evidence}


async def process_one_ai_grade() -> bool:
    if not get_settings().grading_auto_enabled:
        return False
    async with async_session_factory() as db:
        state = InterviewEvaluation.metrics["auto_grading"]["status"].as_string()
        ids = (await db.execute(select(InterviewSession.id).join(InterviewEvaluation,
            InterviewEvaluation.session_id == InterviewSession.id).join(InterviewGradingJob,
            InterviewGradingJob.session_id == InterviewSession.id).where(
                InterviewSession.status == "submitted", InterviewGradingJob.status == "completed",
                InterviewEvaluation.scoring_version == RUBRIC_VERSION,
                (state.is_(None)) | state.in_(["queued", "running", "retry_pending"])
            ).order_by(InterviewSession.submitted_at).limit(30))).scalars().all()
        claimed = None
        for identity in ids:
            session = (await db.execute(select(InterviewSession).where(InterviewSession.id == identity)
                .with_for_update(skip_locked=True))).scalar_one_or_none()
            if session is None:
                continue
            evaluation = (await db.execute(select(InterviewEvaluation).where(
                InterviewEvaluation.session_id == identity).execution_options(populate_existing=True))).scalar_one()
            metrics = copy.deepcopy(evaluation.metrics or {})
            prior = metrics.get("auto_grading") or {}
            now = time.time()
            if prior.get("status") == "running" and prior.get("lease_until", 0) > now:
                await db.rollback()
                continue
            if prior.get("next_attempt_at", 0) > now:
                await db.rollback()
                continue
            if not defense_complete(evaluation):
                metrics["auto_grading"] = queue_state(evaluation)
                evaluation.metrics = metrics
                await db.commit()
                continue
            attempts = prior.get("attempts", 0)
            if attempts >= MAX_ATTEMPTS:
                metrics["auto_grading"] = {**prior, "status": "needs_review", "reason": "retry_limit"}
                evaluation.metrics = metrics
                await db.commit()
                continue
            token = secrets.token_hex(32)
            packet_digest = (metrics.get("assessment") or {}).get("packet_digest")
            metrics["auto_grading"] = {"status": "running", "lease_token": token,
                "lease_until": now + LEASE_SECONDS, "attempts": attempts + 1,
                "packet_digest": packet_digest, "prompt_version": PROMPT_VERSION}
            evaluation.metrics = metrics
            await db.commit()
            claimed = (identity, token, packet_digest, attempts + 1)
            break
        if claimed is None:
            return False
        identity, token, original_digest, attempts = claimed
        try:
            session, job, evaluation, assessment = await review_context(db, identity, None)
            bundle = await _bundle(db, session, job, evaluation, assessment)
            source_digest = job.source_digest
            defense_snapshot = copy.deepcopy(evaluation.metrics.get("defend_answers") or {})
            user_id = session.user_id
            await db.rollback()  # Never hold source/review locks across provider calls.
            first, meta1 = await judge_once(db, user_id=user_id, session_id=identity, bundle=bundle)
            second, meta2 = await judge_once(db, user_id=user_id, session_id=identity, bundle=bundle, audit=True)
            outcome = aggregate_judgments(first, second, bundle)
            outcome.update(packet_digest=original_digest, source_digest=source_digest,
                           model=meta1["model"], input_digest=_digest(bundle))
            final = {"status": outcome["status"], "outcome": outcome,
                     "input_digest": _digest(bundle),
                     "evidence_manifest": [{"id": e["id"], "kind": e["kind"], "digest": _digest(e["content"])} for e in bundle["evidence"]],
                     "defense_snapshot": defense_snapshot, "passes": [first.model_dump(), second.model_dump()],
                     "provider_metadata": [meta1, meta2], "attempts": attempts, "prompt_version": PROMPT_VERSION}
        except asyncio.CancelledError:
            raise  # Durable lease recovers after a terminated worker.
        except Exception:
            await db.rollback()
            final = {"status": "retry_pending" if attempts < MAX_ATTEMPTS else "needs_review",
                     "reason": "grading_unavailable", "next_attempt_at": time.time() + 60,
                     "attempts": attempts, "prompt_version": PROMPT_VERSION}
        await db.execute(select(InterviewSession).where(InterviewSession.id == identity).with_for_update())
        evaluation = (await db.execute(select(InterviewEvaluation).where(
            InterviewEvaluation.session_id == identity).execution_options(populate_existing=True))).scalar_one()
        metrics = copy.deepcopy(evaluation.metrics or {})
        current = metrics.get("auto_grading") or {}
        if (current.get("lease_token") == token and current.get("lease_until", 0) > time.time()
                and (metrics.get("assessment") or {}).get("packet_digest") == original_digest):
            history = metrics.get("auto_grading_history") or []
            if current.get("outcome"):
                history.append(current)
            metrics["auto_grading_history"] = history[-5:]
            metrics["auto_grading"] = final
            evaluation.metrics = metrics
            await db.commit()
        else:
            await db.rollback()
        return True


def candidate_auto_assessment(evaluation) -> dict | None:
    if not get_settings().grading_auto_enabled:
        return None
    metrics = evaluation.metrics or {}
    state = metrics.get("auto_grading") or {}
    outcome = state.get("outcome")
    packet_digest = (metrics.get("assessment") or {}).get("packet_digest")
    if (not outcome or outcome.get("packet_digest") != packet_digest
            or outcome.get("rubric_version") != RUBRIC_VERSION
            or outcome.get("prompt_version") != PROMPT_VERSION):
        return None
    # No raw model outputs, evidence bodies or private source are projected.
    allowed = {"status", "total_score", "rubric_version", "prompt_version", "grader_kind", "authoritative",
               "dimensions", "applicable_weight", "review_flags", "behavioral_score_percent",
               "comparison_notice", "notice", "model"}
    return {key: copy.deepcopy(value) for key, value in outcome.items() if key in allowed}
