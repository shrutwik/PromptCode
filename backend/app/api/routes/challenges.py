from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.models.challenge import Challenge
from app.schemas.challenge import ChallengeCreate, ChallengeListItem, ChallengeResponse

router = APIRouter()


@router.get("/", response_model=list[ChallengeListItem])
async def list_challenges(db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Challenge).order_by(Challenge.created_at.desc())
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


@router.post("/", response_model=ChallengeResponse, status_code=201)
async def create_challenge(
    payload: ChallengeCreate,
    db: AsyncSession = Depends(get_db),
):
    challenge = Challenge(**payload.model_dump())
    db.add(challenge)
    await db.commit()
    await db.refresh(challenge)
    return challenge
