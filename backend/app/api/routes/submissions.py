from __future__ import annotations

import uuid
from pathlib import PurePosixPath

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.challenge import Challenge
from app.models.submission import Submission
from app.models.user import User
from app.schemas.submission import SubmissionCreate, SubmissionReport, SubmissionResponse
from app.workers.queue import enqueue_evaluation_job, process_job

router = APIRouter()


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


@router.get("/", response_model=list[SubmissionResponse])
async def list_submissions(
    challenge_id: uuid.UUID | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    query = (
        select(Submission)
        .where(Submission.user_id == user.id)
        .order_by(Submission.created_at.desc())
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

    submission = Submission(
        challenge_id=payload.challenge_id,
        user_id=user.id,
        code=payload.code,
        entrypoint=payload.entrypoint,
    )
    db.add(submission)
    await db.commit()
    await db.refresh(submission)

    job = await enqueue_evaluation_job(db, submission.id)
    # Opportunistic in-process execution for low-latency MVP behavior.
    # Persistent queue workers can process the same job if this process restarts.
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
