from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.challenge import Challenge
from app.schemas.challenge import ChallengeListItem, ChallengeResponse

router = APIRouter()


@router.get("/", response_model=list[ChallengeListItem])
async def list_challenges(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
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
    db: AsyncSession = Depends(get_db),
):
    challenge = await db.get(Challenge, challenge_id)
    if not challenge:
        raise HTTPException(status_code=404, detail="Challenge not found")
    return challenge
