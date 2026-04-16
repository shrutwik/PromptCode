from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client_ip import client_ip_from_request
from app.core.ratelimit import enforce_rate_limit
from app.db.session import get_db
from app.models.leaderboard import LeaderboardEntry
from app.models.user import User
from app.schemas.leaderboard import LeaderboardEntryResponse

router = APIRouter()

_LEADERBOARD_RATE_LIMIT = 60
_LEADERBOARD_RATE_WINDOW = 60


@router.get("/{challenge_id}", response_model=list[LeaderboardEntryResponse])
async def get_leaderboard(
    challenge_id: uuid.UUID,
    request: Request,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[LeaderboardEntryResponse]:
    await enforce_rate_limit(
        db=db,
        key=f"leaderboard:{client_ip_from_request(request)}",
        limit=_LEADERBOARD_RATE_LIMIT,
        window_seconds=_LEADERBOARD_RATE_WINDOW,
    )
    result = await db.execute(
        select(LeaderboardEntry, User.username.label("username"))
        .join(User, User.id == LeaderboardEntry.user_id, isouter=True)
        .where(LeaderboardEntry.challenge_id == challenge_id)
        .order_by(LeaderboardEntry.score_overall.desc())
        .offset(offset)
        .limit(limit)
    )
    rows = result.all()

    if not rows:
        return []

    response: list[LeaderboardEntryResponse] = []
    for i, row in enumerate(rows, start=1):
        entry = row[0]
        data = LeaderboardEntryResponse.model_validate(entry)
        data.rank = offset + i
        data.username = row.username or "unknown"
        response.append(data)

    return response
