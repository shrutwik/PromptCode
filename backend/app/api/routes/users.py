from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.deps import get_optional_user
from app.db.session import get_db
from app.models.challenge import Challenge
from app.models.submission import Submission
from app.models.user import User
from app.schemas.user import UserProfileResponse, UserPublicResponse

router = APIRouter()


@router.get("/{username}", response_model=UserProfileResponse)
async def get_user_profile(
    username: str,
    viewer: User | None = Depends(get_optional_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    viewer_is_owner = viewer is not None and viewer.id == user.id
    submissions_query = (
        select(Submission)
        .where(Submission.user_id == user.id)
        .order_by(Submission.created_at.desc())
    )
    if not viewer_is_owner:
        submissions_query = submissions_query.where(Submission.status == "completed")

    submissions_result = await db.execute(submissions_query)
    submissions = submissions_result.scalars().all()

    total_challenges_result = await db.execute(select(func.count(Challenge.id)))
    total_challenges = total_challenges_result.scalar() or 0

    completed = [s for s in submissions if s.status == "completed"]
    solved_ids = {s.challenge_id for s in completed if s.score_overall and s.score_overall > 0}

    avg_score = avg_accuracy = avg_efficiency = avg_reliability = avg_orchestration = 0.0
    avg_growth = 0.0
    total_cost = avg_latency = 0.0
    if completed:
        scores = [s.score_overall for s in completed if s.score_overall is not None]
        avg_score = sum(scores) / len(scores) if scores else 0.0
        acc = [s.score_accuracy for s in completed if s.score_accuracy is not None]
        avg_accuracy = sum(acc) / len(acc) if acc else 0.0
        eff = [s.score_efficiency for s in completed if s.score_efficiency is not None]
        avg_efficiency = sum(eff) / len(eff) if eff else 0.0
        rel = [s.score_reliability for s in completed if s.score_reliability is not None]
        avg_reliability = sum(rel) / len(rel) if rel else 0.0
        orc = [s.score_orchestration for s in completed if s.score_orchestration is not None]
        avg_orchestration = sum(orc) / len(orc) if orc else 0.0
        growth = [s.growth_score for s in completed if s.growth_score is not None]
        avg_growth = sum(growth) / len(growth) if growth else 0.0
        total_cost = sum(s.total_cost_usd or 0 for s in completed)
        avg_latency = sum(s.total_latency_ms or 0 for s in completed) / len(completed)

    challenge_ids = {s.challenge_id for s in submissions[:10]}
    challenge_map = {}
    if challenge_ids:
        challenges_result = await db.execute(
            select(Challenge).where(Challenge.id.in_(challenge_ids))
        )
        challenge_map = {c.id: c.title for c in challenges_result.scalars().all()}

    return {
        "user": UserPublicResponse.model_validate(user).model_dump(),
        "stats": {
            "total_submissions": len(submissions),
            "challenges_solved": len(solved_ids),
            "total_challenges": total_challenges,
            "avg_score": round(avg_score, 2),
            "avg_accuracy": round(avg_accuracy, 2),
            "avg_efficiency": round(avg_efficiency, 2),
            "avg_reliability": round(avg_reliability, 2),
            "avg_orchestration": round(avg_orchestration, 2),
            "avg_growth_score": round(avg_growth, 2),
            "total_cost_usd": round(total_cost, 4),
            "avg_latency_ms": round(avg_latency, 0),
        },
        "recent_submissions": [
            {
                "id": str(s.id),
                "challenge_id": str(s.challenge_id),
                "challenge_title": challenge_map.get(s.challenge_id, "Unknown"),
                "status": s.status,
                "score_overall": s.score_overall,
                "growth_score": s.growth_score,
                "total_cost_usd": s.total_cost_usd,
                "created_at": s.created_at,
            }
            for s in submissions[:10]
        ],
    }
