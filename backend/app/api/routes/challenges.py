from __future__ import annotations

import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.client_ip import client_ip_from_request
from app.core.ratelimit import enforce_rate_limit
from app.db.session import get_db
from app.models.challenge import Challenge
from app.schemas.challenge import ChallengeListItem, ChallengeResponse

router = APIRouter()

_CHALLENGE_RATE_LIMIT = 60
_CHALLENGE_RATE_WINDOW = 60


@router.get("/", response_model=list[ChallengeListItem])
async def list_challenges(
    request: Request,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
) -> Sequence[Challenge]:
    await enforce_rate_limit(
        db=db,
        key=f"challenges:{client_ip_from_request(request)}",
        limit=_CHALLENGE_RATE_LIMIT,
        window_seconds=_CHALLENGE_RATE_WINDOW,
    )
    result = await db.execute(
        select(Challenge)
        .order_by(Challenge.category, Challenge.created_at)
        .offset(offset)
        .limit(limit)
    )
    return result.scalars().all()


@router.get("/{challenge_id}", response_model=ChallengeResponse)
async def get_challenge(
    challenge_id: uuid.UUID,
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> Challenge:
    await enforce_rate_limit(
        db=db,
        key=f"challenges:{client_ip_from_request(request)}",
        limit=_CHALLENGE_RATE_LIMIT,
        window_seconds=_CHALLENGE_RATE_WINDOW,
    )
    challenge = await db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge
