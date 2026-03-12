from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import case, func, select
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
) -> dict[str, object]:
    result = await db.execute(select(User).where(User.username == username))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    viewer_is_owner = viewer is not None and viewer.id == user.id
    visible_submission_filters = [Submission.user_id == user.id]
    if not viewer_is_owner:
        visible_submission_filters.append(Submission.status == "completed")

    total_challenges_result = await db.execute(select(func.count(Challenge.id)))
    total_challenges = total_challenges_result.scalar() or 0

    completed_submission = Submission.status == "completed"
    solved_challenge = case(
        (
            completed_submission
            & Submission.score_overall.is_not(None)
            & (Submission.score_overall > 0),
            Submission.challenge_id,
        ),
        else_=None,
    )
    stats_result = await db.execute(
        select(
            func.count(Submission.id).label("total_submissions"),
            func.count(func.distinct(solved_challenge)).label("challenges_solved"),
            func.avg(
                case((completed_submission, Submission.score_overall), else_=None)
            ).label("avg_score"),
            func.avg(
                case((completed_submission, Submission.score_accuracy), else_=None)
            ).label("avg_accuracy"),
            func.avg(
                case((completed_submission, Submission.score_efficiency), else_=None)
            ).label("avg_efficiency"),
            func.avg(
                case((completed_submission, Submission.score_reliability), else_=None)
            ).label("avg_reliability"),
            func.avg(
                case((completed_submission, Submission.score_orchestration), else_=None)
            ).label("avg_orchestration"),
            func.avg(
                case((completed_submission, Submission.growth_score), else_=None)
            ).label("avg_growth_score"),
            func.coalesce(
                func.sum(
                    case(
                        (completed_submission, func.coalesce(Submission.total_cost_usd, 0.0)),
                        else_=0.0,
                    )
                ),
                0.0,
            ).label("total_cost_usd"),
            func.avg(
                case(
                    (completed_submission, func.coalesce(Submission.total_latency_ms, 0.0)),
                    else_=None,
                )
            ).label("avg_latency_ms"),
        ).where(*visible_submission_filters)
    )
    stats = stats_result.one()

    recent_submissions_result = await db.execute(
        select(
            Submission.id,
            Submission.challenge_id,
            Challenge.title.label("challenge_title"),
            Submission.status,
            Submission.score_overall,
            Submission.growth_score,
            Submission.total_cost_usd,
            Submission.created_at,
        )
        .join(Challenge, Challenge.id == Submission.challenge_id, isouter=True)
        .where(*visible_submission_filters)
        .order_by(Submission.created_at.desc())
        .limit(10)
    )
    recent_submissions = recent_submissions_result.all()

    return {
        "user": UserPublicResponse.model_validate(user).model_dump(),
        "stats": {
            "total_submissions": int(stats.total_submissions or 0),
            "challenges_solved": int(stats.challenges_solved or 0),
            "total_challenges": total_challenges,
            "avg_score": round(float(stats.avg_score or 0.0), 2),
            "avg_accuracy": round(float(stats.avg_accuracy or 0.0), 2),
            "avg_efficiency": round(float(stats.avg_efficiency or 0.0), 2),
            "avg_reliability": round(float(stats.avg_reliability or 0.0), 2),
            "avg_orchestration": round(float(stats.avg_orchestration or 0.0), 2),
            "avg_growth_score": round(float(stats.avg_growth_score or 0.0), 2),
            "total_cost_usd": round(float(stats.total_cost_usd or 0.0), 4),
            "avg_latency_ms": round(float(stats.avg_latency_ms or 0.0), 0),
        },
        "recent_submissions": [
            {
                "id": str(row.id),
                "challenge_id": str(row.challenge_id),
                "challenge_title": row.challenge_title or "Unknown",
                "status": row.status,
                "score_overall": row.score_overall,
                "growth_score": row.growth_score,
                "total_cost_usd": row.total_cost_usd,
                "created_at": row.created_at,
            }
            for row in recent_submissions
        ],
    }
