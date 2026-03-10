from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.deps import get_current_user
from app.core.ratelimit import check_rate_limit
from app.db.session import get_db
from app.models.challenge import Challenge
from app.models.evaluation_job import EvaluationJob
from app.models.submission import Submission
from app.models.user import User
from app.schemas.submission import SubmissionCreate, SubmissionReport, SubmissionResponse
from app.workers.queue import enqueue_evaluation_job, process_job

router = APIRouter()

_SUBMISSION_RATE_LIMIT = 5
_SUBMISSION_RATE_WINDOW = 60


def _enforce_submission_rate_limit(*, key: str) -> None:
    if not check_rate_limit(key, limit=_SUBMISSION_RATE_LIMIT, window_seconds=_SUBMISSION_RATE_WINDOW):
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Retry in {_SUBMISSION_RATE_WINDOW}s.",
            headers={"Retry-After": str(_SUBMISSION_RATE_WINDOW)},
        )


def _is_safe_python_entrypoint(entrypoint: str) -> bool:
    normalized = str(entrypoint or "").strip().replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        return False
    path = PurePosixPath(normalized)
    if path.suffix != ".py":
        return False
    parts = path.parts
    if any(p in ("", ".", "..") for p in parts):
        return False
    # Keep submissions to a single script entrypoint for predictable sandbox exec.
    return len(parts) == 1


async def _count_outstanding_jobs_for_user(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> int:
    result = await db.execute(
        select(func.count(EvaluationJob.id))
        .join(Submission, Submission.id == EvaluationJob.submission_id)
        .where(
            Submission.user_id == user_id,
            EvaluationJob.status.in_(("queued", "retry", "running")),
        )
    )
    return int(result.scalar_one() or 0)


async def _guard_submission_capacity(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
) -> None:
    limit = int(get_settings().submission_max_outstanding_jobs_per_user)
    await db.execute(
        select(User.id)
        .where(User.id == user_id)
        .with_for_update()
    )
    outstanding_jobs = await _count_outstanding_jobs_for_user(db, user_id=user_id)
    if outstanding_jobs >= limit:
        raise HTTPException(
            status_code=429,
            detail=(
                "Too many outstanding evaluation jobs. "
                f"Limit is {limit} per user; wait for an active submission to finish."
            ),
        )


@router.get("/", response_model=list[SubmissionResponse])
async def list_submissions(
    challenge_id: uuid.UUID | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Submission)
        .where(Submission.user_id == user.id)
        .order_by(Submission.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if challenge_id:
        query = query.where(Submission.challenge_id == challenge_id)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("/", response_model=SubmissionResponse, status_code=201)
async def create_submission(
    payload: SubmissionCreate,
    background_tasks: BackgroundTasks,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    challenge = await db.get(Challenge, payload.challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    if not _is_safe_python_entrypoint(payload.entrypoint):
        raise HTTPException(
            status_code=400,
            detail="Entrypoint must be a safe Python filename like 'main.py'.",
        )
    _enforce_submission_rate_limit(key=f"submission:{user.id}")
    await _guard_submission_capacity(db, user_id=user.id)

    submission = Submission(
        challenge_id=payload.challenge_id,
        user_id=user.id,
        code=payload.code,
        entrypoint=payload.entrypoint,
    )
    db.add(submission)
    await db.flush()
    job = await enqueue_evaluation_job(db, submission.id, commit=False)
    await db.commit()
    await db.refresh(submission)
    await db.refresh(job)
    if get_settings().submission_inline_queue_processing:
        # Opportunistic in-process execution for low-latency local/dev behavior.
        # Production deployments should rely on the persistent queue worker.
        background_tasks.add_task(process_job, str(job.id))

    return submission


@router.get("/{submission_id}", response_model=SubmissionResponse)
async def get_submission(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    submission = await db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your submission")
    return submission


@router.get("/{submission_id}/status")
async def get_submission_status(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    submission = await db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your submission")
    return {
        "id": str(submission.id),
        "status": submission.status,
        "score_overall": submission.score_overall,
        "completed_at": submission.completed_at.isoformat() if submission.completed_at else None,
    }


@router.get("/{submission_id}/report", response_model=SubmissionReport)
async def get_report(
    submission_id: uuid.UUID,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    submission = await db.get(Submission, submission_id)
    if not submission:
        raise HTTPException(status_code=404, detail="Submission not found")
    if submission.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your submission")
    if submission.status != "completed":
        raise HTTPException(
            status_code=409,
            detail=f"Submission is still '{submission.status}'. Report not ready.",
        )
    if not submission.report:
        raise HTTPException(status_code=404, detail="Report not generated yet")

    return SubmissionReport(**submission.report)
