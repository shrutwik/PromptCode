"""Interview simulation APIs — candidate-safe; never serve SOLUTION.md."""

from __future__ import annotations

import os
import secrets
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client_ip import client_ip_from_request
from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.ratelimit import enforce_rate_limit
from app.db.session import get_db
from app.models.beta_ops import HumanReview
from app.models.interview_session import (
    InterviewAIMessage,
    InterviewEvaluation,
    InterviewSession,
    InterviewSessionEvent,
    InterviewSessionFile,
)
from app.models.user import User
from app.schemas.interview import (
    AIApplyRequest,
    AIChatRequest,
    AIChatResponse,
    AbandonSessionRequest,
    ChallengeProgressCard,
    DashboardSessionItem,
    DashboardStatsResponse,
    DefendAnswerRequest,
    DefendQuestionsResponse,
    DiffFileResponse,
    DiffSummaryResponse,
    EvaluationResponse,
    LevelStepResponse,
    EventRequest,
    EventResponse,
    FileContentResponse,
    FileEntry,
    HumanReviewRequest,
    InterviewChallengeCard,
    InterviewChallengeDetail,
    SaveFileRequest,
    SessionFeedbackRequest,
    SessionFeedbackResponse,
    SessionResponse,
    StartSessionRequest,
    TestRunRequest,
    TestRunResponse,
)
from app.services.interview.ai_provider import (
    SYSTEM_PROMPT,
    AIProviderError,
    AIRequest,
    check_session_ai_rate_limit,
    get_ai_provider,
    mark_session_ai_end,
    mark_session_ai_start,
    validate_context_budget,
)
from app.services.interview.analytics import (
    SCORING_VERSION,
    challenge_quality_metrics,
    funnel_aggregates,
    track_event,
)
from app.services.interview.beta_ops_helpers import require_internal, tag_infra_failure
from app.services.interview.calibration import (
    anonymized_export_row,
    calibration_overview,
    challenge_version_for,
    disagreement_report,
    session_review_payload,
)
from app.services.interview.levels import level_view
from app.services.interview.lifecycle import (
    compute_expires_at,
    maybe_expire_session,
    next_attempt_number,
    require_mutable,
    require_readable,
    utcnow,
)
from app.services.interview.registry import (
    candidate_readme,
    get_challenge,
    get_runner_config,
    is_blocked_path,
    list_challenges,
)
from app.services.interview.rubric import (
    append_accepted_defend_question,
    apply_communication_score,
    candidate_defend_questions,
    parse_defend_questions,
    previous_attempt_for,
    score_session_v2,
    sanitize_candidate_question,
    steps_summary,
)
from app.services.interview.runner import (
    docker_runner_health,
    get_challenge_runner,
    resolve_command_id,
    runner_mode,
)
from app.services.interview.workspace import (
    assert_session_isolation,
    compute_diff_stats,
    create_workspace,
    list_files,
    read_file,
    starter_snapshot_path,
    unified_diff_for_file,
    write_file,
)

router = APIRouter()

_RATE = 120
_WINDOW = 60


def _aware(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _duration_ms(start: datetime | None, end: datetime | None) -> int | None:
    a, b = _aware(start), _aware(end)
    if a is None or b is None:
        return None
    return max(0, int((b - a).total_seconds() * 1000))


def _session_to_response(session: InterviewSession) -> SessionResponse:
    return SessionResponse(
        id=session.id,
        challenge_slug=session.challenge_slug,
        status=session.status,
        owner_token=session.owner_token,
        attempt_number=getattr(session, "attempt_number", 1) or 1,
        started_at=session.started_at,
        submitted_at=session.submitted_at,
        expires_at=getattr(session, "expires_at", None),
    )


def _public_error(detail: str, *, status_code: int = 400) -> HTTPException:
    """User-facing errors without paths/stack traces/Docker internals."""
    return HTTPException(status_code=status_code, detail=detail)


async def _load_owned_session(
    *,
    db: AsyncSession,
    session_id: uuid.UUID,
    user: User,
) -> InterviewSession:
    session = await db.get(InterviewSession, session_id)
    if session is None or session.user_id != user.id:
        # Avoid leaking existence across users
        raise HTTPException(status_code=404, detail="Session not found")
    maybe_expire_session(session)
    return session


def _steps_for_report(evaluation: InterviewEvaluation, timeline: list, slug: str) -> dict:
    stored = (evaluation.metrics or {}).get("steps")
    if isinstance(stored, dict) and "opened" in stored and "total" in stored:
        return stored
    return steps_summary(timeline, slug)


def _candidate_questions(evaluation: InterviewEvaluation, slug: str) -> list[dict]:
    stored = evaluation.defend_questions or []
    if not stored:
        return candidate_defend_questions(slug)
    questions = []
    for i, item in enumerate(stored):
        text = item.get("question", item) if isinstance(item, dict) else str(item)
        questions.append({"question": sanitize_candidate_question(text), "index": i})
    return questions


async def _current_revision(db: AsyncSession, session_id: uuid.UUID, path: str) -> int:
    result = await db.execute(
        select(func.max(InterviewSessionFile.revision)).where(
            InterviewSessionFile.session_id == session_id,
            InterviewSessionFile.path == path,
        )
    )
    value = result.scalar()
    return int(value) if value else 1


async def _stamp_revisions(
    db: AsyncSession, session_id: uuid.UUID, proposed: list[dict]
) -> list[dict]:
    stamped = []
    for edit in proposed:
        path = str(edit.get("path") or "")
        revision = await _current_revision(db, session_id, path) if path else 1
        stamped.append({**edit, "base_revision": revision})
    return stamped


async def _previous_attempt(
    db: AsyncSession, session: InterviewSession, scoring_version: str
) -> dict | None:
    result = await db.execute(
        select(InterviewSession, InterviewEvaluation)
        .join(InterviewEvaluation, InterviewEvaluation.session_id == InterviewSession.id)
        .where(
            InterviewSession.user_id == session.user_id,
            InterviewSession.challenge_slug == session.challenge_slug,
            InterviewSession.status == "submitted",
            InterviewSession.id != session.id,
            InterviewEvaluation.scoring_version == scoring_version,
        )
        .order_by(InterviewSession.submitted_at.desc())
    )
    row = result.first()
    if row is None:
        return None
    prev_session, prev_eval = row
    summary = previous_attempt_for(
        [
            {
                "status": "submitted",
                "scoring_version": prev_eval.scoring_version,
                "total_score": prev_eval.total_score,
                "rubric": prev_eval.rubric,
                "steps": (prev_eval.metrics or {}).get("steps"),
            }
        ],
        scoring_version=scoring_version,
    )
    if summary is None:
        return None
    summary["attempt_number"] = prev_session.attempt_number
    return summary


async def _evaluation_response(
    db: AsyncSession, session: InterviewSession, evaluation: InterviewEvaluation
) -> EvaluationResponse:
    timeline = [
        EventResponse(
            id=e.id,
            event_type=e.event_type,
            payload=e.payload,
            created_at=e.created_at,
        )
        for e in (
            await db.execute(
                select(InterviewSessionEvent)
                .where(InterviewSessionEvent.session_id == session.id)
                .order_by(InterviewSessionEvent.created_at)
            )
        ).scalars().all()
    ]
    return EvaluationResponse(
        total_score=evaluation.total_score,
        rubric=evaluation.rubric,
        metrics={k: v for k, v in (evaluation.metrics or {}).items() if k != "answer_guides"},
        insights=evaluation.insights,
        test_summary=evaluation.test_summary,
        defend_questions=[
            {
                "question": sanitize_candidate_question(
                    q.get("question", q) if isinstance(q, dict) else str(q)
                ),
                "index": i,
            }
            for i, q in enumerate(evaluation.defend_questions or [])
        ],
        timeline=timeline,
        went_well=(evaluation.metrics or {}).get("went_well") or [],
        improve=(evaluation.metrics or {}).get("improve") or [],
        recovery_moments=(evaluation.metrics or {}).get("recovery_moments") or [],
        signals=(evaluation.metrics or {}).get("signals") or [],
        diff_summary=(evaluation.metrics or {}).get("derived", {}).get("diff")
        if isinstance((evaluation.metrics or {}).get("derived"), dict)
        else None,
        scoring_version=getattr(evaluation, "scoring_version", None) or SCORING_VERSION,
        challenge_version=getattr(session, "challenge_version", None),
        steps=_steps_for_report(evaluation, timeline, session.challenge_slug),
        previous_attempt=await _previous_attempt(
            db,
            session,
            getattr(evaluation, "scoring_version", None) or SCORING_VERSION,
        ),
    )


async def _last_event(
    db: AsyncSession, session_id: uuid.UUID
) -> InterviewSessionEvent | None:
    result = await db.execute(
        select(InterviewSessionEvent)
        .where(InterviewSessionEvent.session_id == session_id)
        .order_by(InterviewSessionEvent.created_at.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _add_event(
    db: AsyncSession,
    session_id: uuid.UUID,
    event_type: str,
    payload: dict | None = None,
    *,
    dedupe_file_view: bool = False,
) -> InterviewSessionEvent | None:
    if dedupe_file_view and event_type == "file_viewed":
        last = await _last_event(db, session_id)
        if (
            last
            and last.event_type == "file_viewed"
            and (last.payload or {}).get("path") == (payload or {}).get("path")
        ):
            return last
    event = InterviewSessionEvent(
        session_id=session_id,
        event_type=event_type,
        payload=payload or {},
        # Explicit microsecond timestamps so same-second SQLite events stay ordered.
        created_at=utcnow(),
    )
    db.add(event)
    await db.flush()
    return event


@router.get("/challenges", response_model=list[InterviewChallengeCard])
async def interview_list_challenges(
    request: Request,
    type: str | None = Query(None),
    stack: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[InterviewChallengeCard]:
    await enforce_rate_limit(
        db=db,
        key=f"interview:{client_ip_from_request(request)}",
        limit=_RATE,
        window_seconds=_WINDOW,
    )
    await track_event(db, event_name="challenge_library_viewed", commit=True)
    return [InterviewChallengeCard(**c) for c in list_challenges(type_filter=type, stack_filter=stack)]


@router.get("/challenges/progress", response_model=list[ChallengeProgressCard])
async def challenges_with_progress(
    request: Request,
    type: str | None = Query(None),
    stack: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> list[ChallengeProgressCard]:
    await enforce_rate_limit(
        db=db,
        key=f"interview:{user.id}",
        limit=_RATE,
        window_seconds=_WINDOW,
    )
    cards = list_challenges(type_filter=type, stack_filter=stack)
    sessions = (
        await db.execute(
            select(InterviewSession).where(InterviewSession.user_id == user.id)
        )
    ).scalars().all()
    by_slug: dict[str, list[InterviewSession]] = {}
    for s in sessions:
        maybe_expire_session(s)
        by_slug.setdefault(s.challenge_slug, []).append(s)
    await db.commit()

    out: list[ChallengeProgressCard] = []
    for c in cards:
        sess = by_slug.get(c["slug"], [])
        progress = "not_started"
        best = None
        latest_id = None
        active_id = None
        if sess:
            latest = max(sess, key=lambda x: x.started_at)
            latest_id = latest.id
            if any(s.status in {"created", "active"} for s in sess):
                progress = "in_progress"
                active_id = next(
                    s.id for s in sess if s.status in {"created", "active"}
                )
            if any(s.status == "submitted" for s in sess):
                progress = "completed" if progress != "in_progress" else "in_progress"
            for s in sess:
                if s.status != "submitted":
                    continue
                ev = (
                    await db.execute(
                        select(InterviewEvaluation).where(
                            InterviewEvaluation.session_id == s.id
                        )
                    )
                ).scalar_one_or_none()
                if ev is not None:
                    best = max(best or 0.0, float(ev.total_score))
        out.append(
            ChallengeProgressCard(
                slug=c["slug"],
                title=c["title"],
                type=c["type"],
                stack=c["stack"],
                difficulty=c["difficulty"],
                estimated_minutes=int(c.get("estimated_minutes") or 30),
                summary=c.get("summary") or "",
                progress=progress,
                attempt_count=len(sess),
                best_score=best,
                latest_session_id=latest_id,
                active_session_id=active_id,
            )
        )
    return out


@router.get("/challenges/{slug}", response_model=InterviewChallengeDetail)
async def interview_get_challenge(
    slug: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> InterviewChallengeDetail:
    await enforce_rate_limit(
        db=db,
        key=f"interview:{client_ip_from_request(request)}",
        limit=_RATE,
        window_seconds=_WINDOW,
    )
    meta = get_challenge(slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="Challenge not found")
    await track_event(
        db,
        event_name="challenge_detail_viewed",
        challenge_slug=slug,
        commit=True,
    )
    return InterviewChallengeDetail(
        **{k: meta[k] for k in (
            "slug", "title", "type", "stack", "difficulty",
            "estimated_minutes", "summary", "test_command", "entry_files",
        )},
        readme=candidate_readme(slug),
        command_ids=["run_tests", "run_targeted_tests", "run_benchmark"],
    )


@router.post("/sessions", response_model=SessionResponse)
async def start_session(
    body: StartSessionRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionResponse:
    if (user.beta_status or "active") == "disabled":
        raise HTTPException(status_code=403, detail="Account disabled")
    await enforce_rate_limit(
        db=db,
        key=f"interview-start:{user.id}",
        limit=20,
        window_seconds=_WINDOW,
    )
    meta = get_challenge(body.challenge_slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="Challenge not found")

    session_id = uuid.uuid4()
    owner_token = secrets.token_urlsafe(24)
    attempt = await next_attempt_number(
        db, user_id=user.id, challenge_slug=body.challenge_slug
    )
    try:
        workspace = create_workspace(str(session_id), body.challenge_slug)
        assert_session_isolation(str(session_id), body.challenge_slug)
    except Exception:
        raise _public_error("Could not prepare challenge workspace.", status_code=500)
    now = utcnow()
    session = InterviewSession(
        id=session_id,
        user_id=user.id,
        owner_token=owner_token,
        challenge_slug=body.challenge_slug,
        status="active",
        attempt_number=attempt,
        workspace_path=str(workspace),
        expires_at=compute_expires_at(now),
        started_at=now,
        challenge_version=challenge_version_for(body.challenge_slug),
        scoring_version=SCORING_VERSION,
    )
    db.add(session)
    await _add_event(
        db,
        session_id,
        "session_started",
        {"slug": body.challenge_slug, "attempt": attempt},
    )
    await track_event(
        db,
        event_name="session_started",
        user_id=user.id,
        session_id=session_id,
        challenge_slug=body.challenge_slug,
        properties={"attempt": attempt},
    )
    await db.commit()
    await db.refresh(session)
    return _session_to_response(session)


@router.get("/sessions/{session_id}", response_model=SessionResponse)
async def get_session(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> SessionResponse:
    await enforce_rate_limit(
        db=db,
        key=f"interview:{client_ip_from_request(request)}",
        limit=_RATE,
        window_seconds=_WINDOW,
    )
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    return _session_to_response(session)


async def _level_progress(
    db: AsyncSession, session: InterviewSession
) -> tuple[int, int]:
    result = await db.execute(
        select(InterviewSessionEvent.event_type, InterviewSessionEvent.created_at)
        .where(InterviewSessionEvent.session_id == session.id)
        .order_by(InterviewSessionEvent.created_at.asc())
    )
    index = 0
    tests_on_step = 0
    for event_type, _created in result.all():
        if event_type == "level_advanced":
            index += 1
            tests_on_step = 0
        elif event_type == "test_run":
            tests_on_step += 1
    return index, tests_on_step


@router.get("/sessions/{session_id}/level", response_model=LevelStepResponse)
async def get_session_level(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LevelStepResponse:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    index, tests_on_step = await _level_progress(db, session)
    view = level_view(session.challenge_slug, index, tests_on_step=tests_on_step)
    if view is None:
        raise HTTPException(status_code=404, detail="No steps for this task")
    return LevelStepResponse(**view)


@router.post("/sessions/{session_id}/level/next", response_model=LevelStepResponse)
async def advance_session_level(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> LevelStepResponse:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    require_mutable(session)
    index, tests_on_step = await _level_progress(db, session)
    view = level_view(session.challenge_slug, index, tests_on_step=tests_on_step)
    if view is None:
        raise HTTPException(status_code=404, detail="No steps for this task")
    if view["is_last"]:
        raise HTTPException(status_code=400, detail="This is the last step.")
    if not view["can_advance"]:
        raise HTTPException(
            status_code=400,
            detail="Run the tests for this step before the next one.",
        )
    await _add_event(db, session.id, "level_advanced", {"from_index": index})
    await db.commit()
    nxt = level_view(session.challenge_slug, index + 1, tests_on_step=0)
    assert nxt is not None
    return LevelStepResponse(**nxt)


@router.get("/sessions/{session_id}/files", response_model=list[FileEntry])
async def session_files(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> list[FileEntry]:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    return [FileEntry(**f) for f in list_files(Path(session.workspace_path))]


@router.get("/sessions/{session_id}/files/{file_path:path}", response_model=FileContentResponse)
async def get_session_file(
    session_id: uuid.UUID,
    file_path: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> FileContentResponse:
    if is_blocked_path(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    try:
        content = read_file(Path(session.workspace_path), file_path)
    except FileNotFoundError:
        raise HTTPException(status_code=404, detail="File not found") from None
    except PermissionError:
        raise HTTPException(status_code=404, detail="File not found") from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await _add_event(
        db, session.id, "file_viewed", {"path": file_path}, dedupe_file_view=True
    )
    await db.commit()
    return FileContentResponse(path=file_path, content=content)


@router.put("/sessions/{session_id}/files/{file_path:path}", response_model=FileContentResponse)
async def save_session_file(
    session_id: uuid.UUID,
    file_path: str,
    body: SaveFileRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> FileContentResponse:
    if is_blocked_path(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    require_mutable(session)
    try:
        # Diff against previous content when present for event metadata
        prev = ""
        try:
            prev = read_file(Path(session.workspace_path), file_path)
        except FileNotFoundError:
            prev = ""
        write_file(Path(session.workspace_path), file_path, body.content)
    except PermissionError:
        raise HTTPException(status_code=404, detail="File not found") from None
    from difflib import SequenceMatcher

    additions = deletions = 0
    if body.additions is not None and body.deletions is not None:
        additions, deletions = body.additions, body.deletions
    else:
        for tag, i1, i2, j1, j2 in SequenceMatcher(
            None, prev.splitlines(), body.content.splitlines()
        ).get_opcodes():
            if tag == "insert":
                additions += j2 - j1
            elif tag == "delete":
                deletions += i2 - i1
            elif tag == "replace":
                additions += j2 - j1
                deletions += i2 - i1
    source = body.source if body.source in {"candidate", "ai", "mixed"} else "candidate"
    revision = await _current_revision(db, session.id, file_path) + 1
    db.add(
        InterviewSessionFile(
            session_id=session.id,
            path=file_path,
            content=body.content,
            revision=revision,
        )
    )
    await _add_event(
        db,
        session.id,
        "file_changed",
        {
            "path": file_path,
            "bytes": len(body.content.encode("utf-8")),
            "additions": additions,
            "deletions": deletions,
            "source": source,
        },
    )
    await db.commit()
    return FileContentResponse(path=file_path, content=body.content)


@router.post("/sessions/{session_id}/events", response_model=EventResponse)
async def post_event(
    session_id: uuid.UUID,
    body: EventRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> EventResponse:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    allowed = {
        "session_started",
        "file_viewed",
        "file_searched",
        "file_changed",
        "test_run",
        "test_result",
        "benchmark_run",
        "ai_prompt",
        "ai_response",
        "ai_edit_proposed",
        "ai_edit_accepted",
        "ai_edit_modified",
        "ai_edit_rejected",
        "change_reverted",
        # final_diff_viewed is emitted only via GET /diff?record=true (Review Changes)
        "submission",
        "defend_answer",
    }
    if body.event_type not in allowed:
        raise HTTPException(status_code=400, detail="Unknown event type")
    event = await _add_event(db, session.id, body.event_type, body.payload)
    await db.commit()
    await db.refresh(event)
    return EventResponse(
        id=event.id,
        event_type=event.event_type,
        payload=event.payload,
        created_at=event.created_at,
    )


@router.get("/sessions/{session_id}/events", response_model=list[EventResponse])
async def list_events(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> list[EventResponse]:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    result = await db.execute(
        select(InterviewSessionEvent)
        .where(InterviewSessionEvent.session_id == session.id)
        .order_by(InterviewSessionEvent.created_at)
    )
    events = result.scalars().all()
    return [
        EventResponse(
            id=e.id,
            event_type=e.event_type,
            payload=e.payload,
            created_at=e.created_at,
        )
        for e in events
    ]


@router.post("/sessions/{session_id}/tests", response_model=TestRunResponse)
async def run_session_tests(
    session_id: uuid.UUID,
    request: Request,
    body: TestRunRequest = TestRunRequest(),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> TestRunResponse:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    require_mutable(session)
    meta = get_challenge(session.challenge_slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="Challenge missing")
    try:
        runner_cfg = get_runner_config(session.challenge_slug)
        runner_cfg = {**runner_cfg, "challengeSlug": session.challenge_slug}
    except ValueError as exc:
        raise HTTPException(status_code=500, detail="Challenge runner misconfigured") from exc
    command_id = body.command_id or "run_tests"
    try:
        command = resolve_command_id(
            command_id,
            meta["test_command"],
            commands_map=runner_cfg.get("commands"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Command not allowed") from exc
    event_type = "benchmark_run" if command_id == "run_benchmark" else "test_run"
    await _add_event(
        db, session.id, event_type, {"command_id": command_id, "command": command}
    )
    await db.commit()
    runner = get_challenge_runner()
    timeout = int(runner_cfg.get("timeoutSeconds") or 60)
    run_kwargs = {
        "timeout_seconds": timeout,
        "command_id": command_id,
        "runner_config": runner_cfg,
    }
    try:
        if command_id == "run_targeted_tests":
            result = await runner.run_targeted_tests(
                Path(session.workspace_path), command, **run_kwargs
            )
        elif command_id == "run_benchmark":
            result = await runner.run_benchmark(
                Path(session.workspace_path), command, **run_kwargs
            )
        else:
            result = await runner.run_tests(
                Path(session.workspace_path), command, **run_kwargs
            )
    except Exception:
        tag_infra_failure(session, "runner", blocked_ms=0)
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Test runner temporarily unavailable. Try again shortly.",
        )
    session.test_run_count = int(getattr(session, "test_run_count", 0) or 0) + 1
    session.runner_duration_ms = int(getattr(session, "runner_duration_ms", 0) or 0) + int(
        result.get("duration_ms") or 0
    )
    if result.get("error_code") in {"runner_busy", "image_missing", "docker_error"}:
        tag_infra_failure(session, "docker", blocked_ms=int(result.get("duration_ms") or 0))
    elif result.get("timed_out"):
        # Candidate code timeouts are not infra — only tag when isolation/runner fails.
        if (result.get("isolation") or {}).get("error"):
            tag_infra_failure(session, "runner", blocked_ms=int(result.get("duration_ms") or 0))
    await _add_event(
        db,
        session.id,
        "test_result",
        {
            "ok": result["ok"],
            "exit_code": result["exit_code"],
            "command": result["command"],
            "command_id": command_id,
            "duration_ms": result.get("duration_ms"),
            "counts": result.get("counts"),
            "mode": result.get("mode"),
            "timed_out": result.get("timed_out"),
            "isolation": result.get("isolation"),
            "runner": result.get("runner"),
            "error_code": result.get("error_code"),
        },
    )
    await db.commit()
    return TestRunResponse(**result)


@router.post("/sessions/{session_id}/ai/chat", response_model=AIChatResponse)
async def ai_chat(
    session_id: uuid.UUID,
    body: AIChatRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> AIChatResponse:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    require_mutable(session)

    settings = get_settings()
    if int(getattr(session, "ai_request_count", 0) or 0) >= int(
        settings.interview_max_ai_requests_per_session
    ):
        raise HTTPException(
            status_code=429,
            detail="AI request limit reached for this session.",
        )

    sid = str(session.id)
    try:
        check_session_ai_rate_limit(sid)
    except AIProviderError as exc:
        raise HTTPException(status_code=429, detail=exc.message) from exc

    # Attach only explicitly requested files — never dump whole repo / hidden paths.
    attachments: list[dict[str, str]] = []
    rejected_attachments: list[str] = []
    for rel in body.attached_paths:
        if is_blocked_path(rel):
            rejected_attachments.append(rel)
            continue
        if len(attachments) >= 6:
            rejected_attachments.append(rel)
            continue
        try:
            content = read_file(Path(session.workspace_path), rel)
            attachments.append({"path": rel, "content": content})
        except (FileNotFoundError, PermissionError, ValueError):
            rejected_attachments.append(rel)

    budget_errors = validate_context_budget(
        prompt=body.message,
        attachments=attachments,
        selected_text=body.selected_text,
    )
    if budget_errors:
        raise HTTPException(
            status_code=400,
            detail={
                "message": "AI context rejected — nothing was silently dropped.",
                "errors": budget_errors,
                "rejected_attachments": rejected_attachments,
            },
        )

    db.add(
        InterviewAIMessage(
            session_id=session.id,
            role="user",
            content=body.message,
            meta={
                "attached": [a["path"] for a in attachments],
                "rejected_attachments": rejected_attachments,
                "include_test_output": body.include_test_output,
                "has_selection": bool(body.selected_text),
            },
        )
    )
    await _add_event(
        db,
        session.id,
        "ai_prompt",
        {
            "chars": len(body.message),
            "message": body.message[:4000],
            "attached": [a["path"] for a in attachments],
            "rejected_attachments": rejected_attachments,
            "include_test_output": body.include_test_output,
        },
    )
    await db.commit()

    provider = get_ai_provider()
    mark_session_ai_start(sid)
    session.ai_request_count = int(getattr(session, "ai_request_count", 0) or 0) + 1
    try:
        ai_result = await provider.complete_request(
            AIRequest(
                prompt=body.message,
                system=SYSTEM_PROMPT,
                attachments=attachments,
                selected_text=body.selected_text,
                include_test_output=body.include_test_output,
                session_id=sid,
            )
        )
    except AIProviderError as exc:
        # Operational failure — keep prompt event; do not invent scoring penalties.
        tag_infra_failure(session, f"ai:{exc.code}", blocked_ms=0)
        await _add_event(
            db,
            session.id,
            "ai_provider_error",
            {
                "code": exc.code,
                "retryable": exc.retryable,
                "message": exc.message,
            },
        )
        await db.commit()
        raise HTTPException(
            status_code=503 if exc.retryable else 400,
            detail={"code": exc.code, "message": exc.message, "scoring_impact": None},
        ) from exc
    finally:
        mark_session_ai_end(sid)

    reply = ai_result.text
    proposed: list[dict] = list(ai_result.proposed_edits)
    if not proposed:
        import re

        for m in re.finditer(
            r"```[\w.+-]*\n(?:#|//)\s*file:\s*([^\n]+)\n(.*?)```",
            reply,
            re.S | re.I,
        ):
            proposed.append({"path": m.group(1).strip(), "content": m.group(2)})
    proposed = await _stamp_revisions(db, session.id, proposed)
    if proposed:
        await _add_event(
            db,
            session.id,
            "ai_edit_proposed",
            {
                "paths": [p["path"] for p in proposed],
                "count": len(proposed),
                "revisions": {p["path"]: p.get("base_revision") for p in proposed},
            },
        )

    db.add(
        InterviewAIMessage(
            session_id=session.id,
            role="assistant",
            content=reply,
            meta={
                "provider": ai_result.provider,
                "model": ai_result.model,
                "proposed_edits": len(proposed),
                "latency_ms": ai_result.latency_ms,
                "usage": ai_result.usage,
            },
        )
    )
    await _add_event(
        db,
        session.id,
        "ai_response",
        {
            "provider": ai_result.provider,
            "model": ai_result.model,
            "chars": len(reply),
            "latency_ms": ai_result.latency_ms,
            "usage": ai_result.usage,
        },
    )
    await db.commit()
    return AIChatResponse(
        reply=reply,
        provider=ai_result.provider,
        model=ai_result.model,
        proposed_edits=proposed,
        latency_ms=ai_result.latency_ms,
        rejected_attachments=rejected_attachments,
        error_code=ai_result.error_code,
    )


@router.post("/sessions/{session_id}/ai/apply", response_model=FileContentResponse)
async def ai_apply_edit(
    session_id: uuid.UUID,
    body: AIApplyRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> FileContentResponse:
    """Practical Apply workflow with candidate/ai/mixed attribution."""
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    require_mutable(session)
    if is_blocked_path(body.path):
        raise HTTPException(status_code=404, detail="File not found")
    disposition = body.disposition if body.disposition in {
        "accepted", "modified", "rejected"
    } else "accepted"
    event_map = {
        "accepted": "ai_edit_accepted",
        "modified": "ai_edit_modified",
        "rejected": "ai_edit_rejected",
    }
    if disposition == "rejected":
        await _add_event(
            db,
            session.id,
            event_map[disposition],
            {"path": body.path, "disposition": disposition},
        )
        await db.commit()
        try:
            content = read_file(Path(session.workspace_path), body.path)
        except FileNotFoundError:
            content = ""
        return FileContentResponse(path=body.path, content=content)

    if body.base_revision is None:
        raise HTTPException(
            status_code=400,
            detail="This suggestion has no file revision. Ask again.",
        )
    current = await _current_revision(db, session.id, body.path)
    if int(body.base_revision) != current:
        raise HTTPException(
            status_code=409,
            detail="The file changed since this suggestion. Re-ask or edit by hand.",
        )
    payload = {
        "path": body.path,
        "disposition": disposition,
        "base_revision": current,
    }
    if disposition == "modified":
        payload["content"] = body.content
        payload["proposed_content"] = body.proposed_content or ""
    await _add_event(db, session.id, event_map[disposition], payload)
    source = "ai" if disposition == "accepted" else "mixed"
    write_file(Path(session.workspace_path), body.path, body.content)
    db.add(
        InterviewSessionFile(
            session_id=session.id,
            path=body.path,
            content=body.content,
            revision=current + 1,
        )
    )
    await _add_event(
        db,
        session.id,
        "file_changed",
        {
            "path": body.path,
            "bytes": len(body.content.encode("utf-8")),
            "source": source,
        },
    )
    await db.commit()
    return FileContentResponse(path=body.path, content=body.content)


@router.post("/sessions/{session_id}/submit", response_model=EvaluationResponse)
async def submit_session(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> EvaluationResponse:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    # Idempotent: already submitted → return existing report
    if session.status == "submitted":
        existing = (
            await db.execute(
                select(InterviewEvaluation).where(
                    InterviewEvaluation.session_id == session.id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return await _evaluation_response(db, session, existing)
    maybe_expire_session(session)
    if session.status == "expired":
        raise HTTPException(
            status_code=410,
            detail="Session expired before submit. Start a new attempt.",
        )
    if session.status not in {"created", "active"}:
        raise HTTPException(status_code=409, detail="Session cannot be submitted.")

    meta = get_challenge(session.challenge_slug)
    if meta is None:
        raise HTTPException(status_code=404, detail="Challenge missing")

    # Do NOT auto-emit final_diff_viewed — only when candidate opens Review Changes.
    await _add_event(db, session.id, "submission", {})
    try:
        runner_cfg = get_runner_config(session.challenge_slug)
        runner_cfg = {**runner_cfg, "challengeSlug": session.challenge_slug}
        command = resolve_command_id(
            "run_tests",
            meta["test_command"],
            commands_map=runner_cfg.get("commands"),
        )
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
    runner = get_challenge_runner()
    test_result = await runner.run_tests(
        Path(session.workspace_path),
        command,
        timeout_seconds=int(runner_cfg.get("timeoutSeconds") or 60),
        command_id="run_tests",
        runner_config=runner_cfg,
    )
    await _add_event(
        db,
        session.id,
        "test_result",
        {
            "ok": test_result["ok"],
            "exit_code": test_result["exit_code"],
            "final": True,
            "duration_ms": test_result.get("duration_ms"),
            "counts": test_result.get("counts"),
            "timed_out": test_result.get("timed_out"),
            "isolation": test_result.get("isolation"),
            "runner": test_result.get("runner"),
        },
    )

    events_result = await db.execute(
        select(InterviewSessionEvent)
        .where(InterviewSessionEvent.session_id == session.id)
        .order_by(InterviewSessionEvent.created_at)
    )
    event_rows = list(events_result.scalars().all())
    events = [
        {
            "id": e.id,
            "event_type": e.event_type,
            "payload": e.payload,
            "created_at": e.created_at,
        }
        for e in event_rows
    ]
    prompts_result = await db.execute(
        select(InterviewAIMessage).where(
            InterviewAIMessage.session_id == session.id,
            InterviewAIMessage.role == "user",
        )
    )
    prompts = [m.content for m in prompts_result.scalars().all()]
    starter = starter_snapshot_path(str(session.id))
    scored = score_session_v2(
        events=events,
        test_summary=test_result,
        ai_prompts=prompts,
        challenge_slug=session.challenge_slug,
        workspace=Path(session.workspace_path),
        starter_root=starter if starter.exists() else None,
    )
    # Defend questions only after submit — parsed server-side from SOLUTION.md
    defend = parse_defend_questions(session.challenge_slug)
    # Candidate report: questions only (guides kept server-side for interviewer tooling)
    defend_for_candidate = append_accepted_defend_question(
        candidate_defend_questions(session.challenge_slug),
        events,
    )

    session.status = "submitted"
    session.submitted_at = datetime.now(timezone.utc)
    wall = _duration_ms(session.started_at, session.submitted_at)
    if wall is not None:
        session.wall_duration_ms = wall
        blocked = int(session.infra_blocked_ms or 0)
        session.active_duration_ms = max(0, wall - blocked)
    session.scoring_version = SCORING_VERSION
    if not session.challenge_version:
        session.challenge_version = challenge_version_for(session.challenge_slug)
    evaluation = InterviewEvaluation(
        session_id=session.id,
        total_score=scored["total_score"],
        rubric=scored["rubric"],
        metrics={
            **scored["metrics"],
            "went_well": scored.get("went_well", []),
            "improve": scored.get("improve", []),
            "recovery_moments": scored.get("recovery_moments", []),
            "defend_answers": {},
            "answer_guides": defend,  # server-stored; stripped from candidate response below
        },
        insights=scored["insights"],
        test_summary={
            "ok": test_result["ok"],
            "exit_code": test_result["exit_code"],
            "command": test_result["command"],
            "duration_ms": test_result.get("duration_ms"),
            "counts": test_result.get("counts"),
            "stdout_tail": test_result["stdout"][-4000:],
            "stderr_tail": test_result["stderr"][-2000:],
            # Honest: no hidden evaluator leakage
            "correctness_visible": test_result["ok"],
            "hidden_tests_leaked": False,
        },
        defend_questions=defend_for_candidate,
        scoring_version=SCORING_VERSION,
    )
    db.add(evaluation)
    await track_event(
        db,
        event_name="session_submitted",
        user_id=session.user_id,
        session_id=session.id,
        challenge_slug=session.challenge_slug,
        properties={"total_score": scored["total_score"], "scoring_version": SCORING_VERSION},
    )
    await db.commit()
    return await _evaluation_response(db, session, evaluation)


@router.get("/sessions/{session_id}/diff", response_model=DiffSummaryResponse)
async def session_diff_summary(
    session_id: uuid.UUID,
    request: Request,
    record: bool = Query(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> DiffSummaryResponse:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    starter = starter_snapshot_path(str(session.id))
    if not starter.exists():
        raise HTTPException(status_code=404, detail="Starter snapshot missing")
    stats = compute_diff_stats(starter, Path(session.workspace_path))
    if record:
        await _add_event(db, session.id, "final_diff_viewed", {"file_count": stats["file_count"]})
        await db.commit()
    return DiffSummaryResponse(**stats)


@router.get("/sessions/{session_id}/diff/{file_path:path}", response_model=DiffFileResponse)
async def session_diff_file(
    session_id: uuid.UUID,
    file_path: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> DiffFileResponse:
    if is_blocked_path(file_path):
        raise HTTPException(status_code=404, detail="File not found")
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    starter = starter_snapshot_path(str(session.id))
    try:
        unified = unified_diff_for_file(
            starter, Path(session.workspace_path), file_path
        )
    except PermissionError:
        raise HTTPException(status_code=404, detail="File not found") from None
    return DiffFileResponse(path=file_path, unified=unified)


@router.get(
    "/sessions/{session_id}/defend", response_model=DefendQuestionsResponse
)
async def get_defend(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> DefendQuestionsResponse:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    if session.status != "submitted":
        raise HTTPException(status_code=400, detail="Submit before defend")
    ev = (
        await db.execute(
            select(InterviewEvaluation).where(InterviewEvaluation.session_id == session.id)
        )
    ).scalar_one_or_none()
    if ev is None:
        raise HTTPException(status_code=404, detail="Report not ready")
    answers = (ev.metrics or {}).get("defend_answers") or {}
    # Never return answer_guide to candidate
    questions = _candidate_questions(ev, session.challenge_slug)
    await track_event(
        db,
        event_name="defend_started",
        user_id=user.id,
        session_id=session.id,
        challenge_slug=session.challenge_slug,
        commit=True,
    )
    return DefendQuestionsResponse(questions=questions, answers=answers)


@router.post(
    "/sessions/{session_id}/defend", response_model=DefendQuestionsResponse
)
async def post_defend_answer(
    session_id: uuid.UUID,
    body: DefendAnswerRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> DefendQuestionsResponse:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    if session.status != "submitted":
        raise HTTPException(status_code=400, detail="Submit before defend")
    ev = (
        await db.execute(
            select(InterviewEvaluation).where(InterviewEvaluation.session_id == session.id)
        )
    ).scalar_one_or_none()
    if ev is None:
        raise HTTPException(status_code=404, detail="Report not ready")
    metrics = dict(ev.metrics or {})
    answers = dict(metrics.get("defend_answers") or {})
    answers[str(body.index)] = body.answer[:4000]
    metrics["defend_answers"] = answers
    if (ev.scoring_version or "") == "v2":
        rubric, total = apply_communication_score(ev.rubric or {}, list(answers.values()))
        ev.rubric = rubric
        ev.total_score = total
    ev.metrics = metrics
    await _add_event(
        db,
        session.id,
        "defend_answer",
        {"index": body.index, "chars": len(body.answer), "answer": body.answer[:4000]},
    )
    questions = _candidate_questions(ev, session.challenge_slug)
    if len(answers) >= len(questions):
        await track_event(
            db,
            event_name="defend_completed",
            user_id=user.id,
            session_id=session.id,
            challenge_slug=session.challenge_slug,
        )
    await db.commit()
    return DefendQuestionsResponse(questions=questions, answers=answers)


@router.get("/sessions/{session_id}/report", response_model=EvaluationResponse)
async def get_report(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
    x_session_token: str | None = Header(None, alias="X-Session-Token"),
) -> EvaluationResponse:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    result = await db.execute(
        select(InterviewEvaluation).where(InterviewEvaluation.session_id == session.id)
    )
    evaluation = result.scalar_one_or_none()
    if evaluation is None:
        raise HTTPException(status_code=404, detail="Report not ready — submit first")
    await track_event(
        db,
        event_name="report_viewed",
        user_id=user.id,
        session_id=session.id,
        challenge_slug=session.challenge_slug,
        commit=True,
    )
    return await _evaluation_response(db, session, evaluation)


@router.get("/dashboard", response_model=DashboardStatsResponse)
async def dashboard(
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> DashboardStatsResponse:
    await enforce_rate_limit(
        db=db,
        key=f"interview:{user.id}",
        limit=_RATE,
        window_seconds=_WINDOW,
    )
    q = (
        select(InterviewSession)
        .where(InterviewSession.user_id == user.id)
        .order_by(InterviewSession.started_at.desc())
        .limit(50)
    )
    sessions = (await db.execute(q)).scalars().all()
    items: list[DashboardSessionItem] = []
    scores: list[float] = []
    correctness: list[float] = []
    exploration: list[float] = []
    ai_judgment: list[float] = []
    verification: list[float] = []
    for s in sessions:
        maybe_expire_session(s)
        ev = (
            await db.execute(
                select(InterviewEvaluation).where(InterviewEvaluation.session_id == s.id)
            )
        ).scalar_one_or_none()
        items.append(
            DashboardSessionItem(
                id=s.id,
                challenge_slug=s.challenge_slug,
                status=s.status,
                attempt_number=getattr(s, "attempt_number", 1) or 1,
                started_at=s.started_at,
                submitted_at=s.submitted_at,
                total_score=ev.total_score if ev else None,
            )
        )
        if ev is not None:
            scores.append(float(ev.total_score))
            rub = ev.rubric or {}
            if "A_correctness" in rub:
                correctness.append(float(rub["A_correctness"].get("score", 0)))
            if "B_investigation" in rub:
                exploration.append(float(rub["B_investigation"].get("score", 0)))
            if "D_ai_leverage" in rub:
                ai_judgment.append(float(rub["D_ai_leverage"].get("score", 0)))
            if "E_verification" in rub:
                verification.append(float(rub["E_verification"].get("score", 0)))

    def _avg(xs: list[float]) -> float | None:
        return round(sum(xs) / len(xs), 1) if xs else None

    completed = sum(1 for s in items if s.status == "submitted")
    trends: list[str] = []
    trends_note = None
    if completed == 0:
        trends_note = "Complete a challenge to see your practice history here."
    elif completed < 3:
        trends_note = "Behavioral trends appear after at least 3 completed sessions."
    else:
        half = max(1, len(scores) // 2)
        early = _avg(scores[-half:])
        late = _avg(scores[:half])
        if early is not None and late is not None:
            if late > early + 3:
                trends.append("Recent sessions score higher than earlier ones.")
            elif early > late + 3:
                trends.append("Earlier sessions scored higher than recent ones.")
            else:
                trends.append("Scores are relatively stable across recent sessions.")

    await db.commit()
    return DashboardStatsResponse(
        sessions=items,
        completed=completed,
        avg_score=_avg(scores),
        avg_correctness=_avg(correctness),
        avg_exploration=_avg(exploration),
        avg_ai_judgment=_avg(ai_judgment),
        avg_verification=_avg(verification),
        trends=trends,
        trends_note=trends_note,
    )



@router.post(
    "/sessions/{session_id}/feedback",
    response_model=SessionFeedbackResponse,
)
async def submit_feedback(
    session_id: uuid.UUID,
    body: SessionFeedbackRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionFeedbackResponse:
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    if session.status != "submitted":
        raise HTTPException(status_code=400, detail="Feedback is available after submit.")
    settings = get_settings()
    session.feedback_realism = body.realism
    session.feedback_difficulty = body.difficulty
    session.feedback_text = (body.text or "")[:2000]
    ev = (
        await db.execute(
            select(InterviewEvaluation).where(InterviewEvaluation.session_id == session.id)
        )
    ).scalar_one_or_none()
    session.feedback_meta = {
        "challenge_slug": session.challenge_slug,
        "session_id": str(session.id),
        "user_id": str(user.id),
        "user_agent": (request.headers.get("user-agent") or "")[:200],
        "app_version": settings.app_version,
        "git_sha": settings.git_sha or None,
        "runner": runner_mode(),
        "ai_as_expected": body.ai_as_expected,
        "confusing_or_broken": body.confusing_or_broken,
        "most_like_real_interview": body.most_like_real_interview,
        "total_score": ev.total_score if ev else None,
        "scoring_version": (ev.scoring_version if ev else None) or session.scoring_version,
        "wall_duration_ms": session.wall_duration_ms,
        "active_duration_ms": session.active_duration_ms,
    }
    await track_event(
        db,
        event_name="feedback_submitted",
        user_id=user.id,
        session_id=session.id,
        challenge_slug=session.challenge_slug,
        properties={
            "realism": body.realism,
            "difficulty": body.difficulty,
            "ai_as_expected": body.ai_as_expected,
            "confusing_or_broken": body.confusing_or_broken,
            "most_like_real_interview": body.most_like_real_interview,
        },
    )
    await db.commit()
    return SessionFeedbackResponse(ok=True)


@router.post(
    "/sessions/{session_id}/abandon",
    response_model=SessionFeedbackResponse,
)
async def abandon_session(
    session_id: uuid.UUID,
    body: AbandonSessionRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
) -> SessionFeedbackResponse:
    """Optional reason when returning to dashboard — not a blocking mid-interview modal."""
    session = await _load_owned_session(db=db, session_id=session_id, user=user)
    if session.status not in {"created", "active"}:
        raise HTTPException(status_code=400, detail="Session is not active.")
    session.abandon_reason = (body.reason or "")[:256] or None
    await track_event(
        db,
        event_name="session_abandoned",
        user_id=user.id,
        session_id=session.id,
        challenge_slug=session.challenge_slug,
        properties={"reason": session.abandon_reason},
    )
    await db.commit()
    return SessionFeedbackResponse(ok=True)


@router.get("/internal/diagnostics")
async def interview_diagnostics(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Protected beta diagnostics — not a public admin panel."""
    require_internal(request)
    settings = get_settings()
    from sqlalchemy import func

    active = (
        await db.execute(
            select(func.count()).select_from(InterviewSession).where(
                InterviewSession.status.in_(("created", "active"))
            )
        )
    ).scalar_one()
    expired = (
        await db.execute(
            select(func.count()).select_from(InterviewSession).where(
                InterviewSession.status == "expired"
            )
        )
    ).scalar_one()
    report = docker_runner_health(probe_exec=False)
    return {
        "version": settings.app_version,
        "git_sha": settings.git_sha or os.getenv("GIT_SHA") or os.getenv("PROMPTCODE_GIT_SHA") or "",
        "debug": settings.debug,
        "runner_mode": runner_mode(),
        "runner": report,
        "ai_configured": bool(settings.openai_api_key),
        "session_ttl_hours": settings.session_ttl_hours,
        "max_runners": settings.max_runners,
        "active_sessions": int(active or 0),
        "expired_sessions": int(expired or 0),
        "auth_cookie_enabled": settings.auth_cookie_enabled,
        "beta_invite_required": settings.beta_invite_required,
        "starter_challenge": settings.beta_starter_challenge,
        "scoring_version": SCORING_VERSION,
    }


@router.get("/internal/analytics/funnel")
async def internal_analytics_funnel(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_internal(request)
    return await funnel_aggregates(db)


@router.get("/internal/analytics/challenges")
async def internal_analytics_challenges(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_internal(request)
    return {"challenges": await challenge_quality_metrics(db)}


@router.get("/internal/calibration")
async def internal_calibration(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_internal(request)
    return await calibration_overview(db)


@router.get("/internal/calibration/disagreements")
async def internal_disagreements(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_internal(request)
    return await disagreement_report(db)


@router.get("/internal/sessions/{session_id}/review")
async def internal_session_review(
    session_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_internal(request)
    payload = await session_review_payload(db, session_id)
    if payload is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return payload


@router.post("/internal/sessions/{session_id}/review")
async def internal_human_review(
    session_id: uuid.UUID,
    body: HumanReviewRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_internal(request)
    session = (
        await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    ).scalar_one_or_none()
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    review = HumanReview(
        session_id=session_id,
        reviewer=(body.reviewer or "internal")[:128],
        notes=(body.notes or "")[:4000],
        category_observations=body.category_observations or {},
        disagreement=bool(body.disagreement),
        observed_difficulty=body.observed_difficulty,
        observed_time_minutes=body.observed_time_minutes,
    )
    db.add(review)
    await db.commit()
    await db.refresh(review)
    return {
        "ok": True,
        "review_id": str(review.id),
        "note": "human_review stored separately from automated_score",
    }


@router.get("/internal/users")
async def internal_list_users(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_internal(request)
    users = (await db.execute(select(User).order_by(User.created_at.desc()).limit(200))).scalars().all()
    out = []
    for u in users:
        sess_count = (
            await db.execute(
                select(func.count()).select_from(InterviewSession).where(
                    InterviewSession.user_id == u.id
                )
            )
        ).scalar_one()
        out.append(
            {
                "id": str(u.id),
                "email": u.email,
                "username": u.username,
                "beta_status": u.beta_status,
                "beta_cohort": u.beta_cohort,
                "signup_source": u.signup_source,
                "created_at": u.created_at.isoformat() if u.created_at else None,
                "last_login_at": u.last_login_at.isoformat() if u.last_login_at else None,
                "session_count": int(sess_count or 0),
            }
        )
    return {"users": out}


@router.post("/internal/users/{user_id}/disable")
async def internal_disable_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_internal(request)
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.beta_status = "disabled"
    await db.commit()
    return {"ok": True, "beta_status": "disabled"}


@router.post("/internal/users/{user_id}/enable")
async def internal_enable_user(
    user_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_internal(request)
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    user.beta_status = "active"
    await db.commit()
    return {"ok": True, "beta_status": "active"}


@router.get("/internal/export/calibration")
async def internal_export_calibration(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    require_internal(request)
    sessions = (await db.execute(select(InterviewSession))).scalars().all()
    evals = {
        e.session_id: e
        for e in (await db.execute(select(InterviewEvaluation))).scalars().all()
    }
    reviews = {
        r.session_id: r
        for r in (await db.execute(select(HumanReview))).scalars().all()
    }
    rows = [
        anonymized_export_row(s, evals.get(s.id), reviews.get(s.id)) for s in sessions
    ]
    return {"rows": rows, "n": len(rows), "note": "No email/name/secrets/full prompts"}


@router.get("/internal/incidents")
async def internal_incidents(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Lightweight incident visibility — not PagerDuty."""
    require_internal(request)
    from sqlalchemy import func

    failed = (
        await db.execute(
            select(func.count()).select_from(InterviewSession).where(
                InterviewSession.status == "failed"
            )
        )
    ).scalar_one()
    tagged = (
        await db.execute(
            select(InterviewSession).where(InterviewSession.infra_failure_tags.is_not(None)).limit(50)
        )
    ).scalars().all()
    return {
        "failed_sessions": int(failed or 0),
        "recent_infra_tagged": [
            {
                "session_id": str(s.id),
                "challenge_slug": s.challenge_slug,
                "tags": s.infra_failure_tags,
                "failed_reason": s.failed_reason,
            }
            for s in tagged
        ],
        "thresholds_doc": "docs/beta-operations.md#alert-thresholds",
    }


@router.get("/internal/disk")
async def internal_disk(request: Request) -> dict:
    require_internal(request)
    settings = get_settings()
    root = Path(settings.interview_workspace_root or "/tmp/promptcode-interview")
    total = 0
    count = 0
    if root.exists():
        for p in root.rglob("*"):
            if p.is_file():
                try:
                    total += p.stat().st_size
                    count += 1
                except OSError:
                    pass
    return {
        "workspace_root": str(root),
        "file_count": count,
        "bytes": total,
        "note": "Docker disk: docker system df (operator)",
    }


@router.get("/internal/runner-health")
async def interview_runner_health(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Admin/internal Docker runner diagnostic.

    Available when PROMPTCODE_DEBUG=true, or with header X-PromptCode-Internal: 1
    in non-debug only if PROMPTCODE_INTERVIEW_INTERNAL_TOKEN matches.
    """
    settings = get_settings()
    internal_token = (request.headers.get("X-PromptCode-Internal-Token") or "").strip()
    expected = (os.getenv("PROMPTCODE_INTERVIEW_INTERNAL_TOKEN") or "").strip()
    allowed = bool(settings.debug) or (expected and internal_token == expected)
    if not allowed:
        raise HTTPException(status_code=404, detail="Not found")
    await enforce_rate_limit(
        db=db,
        key=f"interview-health:{client_ip_from_request(request)}",
        limit=30,
        window_seconds=60,
    )
    report = docker_runner_health(probe_exec=True)
    report["configured_mode"] = runner_mode()
    return report
