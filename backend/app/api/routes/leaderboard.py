from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.leaderboard import LeaderboardEntry
from app.models.user import User
from app.schemas.leaderboard import LeaderboardEntryResponse

router = APIRouter()


@router.get("/{challenge_id}", response_model=list[LeaderboardEntryResponse])
async def get_leaderboard(
    challenge_id: uuid.UUID,
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> list[LeaderboardEntryResponse]:
    result = await db.execute(
        select(LeaderboardEntry)
        .where(LeaderboardEntry.challenge_id == challenge_id)
        .order_by(LeaderboardEntry.score_overall.desc())
        .offset(offset)
        .limit(limit)
    )
    entries = result.scalars().all()

    if not entries:
        return []

    user_ids = {e.user_id for e in entries}
    users_result = await db.execute(select(User).where(User.id.in_(user_ids)))
    user_map = {u.id: u.username for u in users_result.scalars().all()}

    response: list[LeaderboardEntryResponse] = []
    for i, entry in enumerate(entries, start=1):
        data = LeaderboardEntryResponse.model_validate(entry)
        data.rank = offset + i
        data.username = user_map.get(entry.user_id, "unknown")
        response.append(data)

    return response
