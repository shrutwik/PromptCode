from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

import app.models  # noqa: F401 - ensure ORM models are registered
from app.core.ratelimit import cleanup_expired_counters, enforce_rate_limit
from app.db.base import Base
from app.models.rate_limit_counter import RateLimitCounter


def _build_session_factory(tmp_path) -> tuple[async_sessionmaker[AsyncSession], object]:
    db_file = tmp_path / "ratelimit.db"
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_file}")
    session_factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async def _create_schema() -> None:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    asyncio.run(_create_schema())
    return session_factory, engine


def test_allows_requests_within_limit(tmp_path) -> None:
    session_factory, engine = _build_session_factory(tmp_path)

    async def exercise() -> None:
        started_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        for attempt in range(5):
            async with session_factory() as db:
                await enforce_rate_limit(
                    db=db,
                    key="ip:1.2.3.4",
                    limit=5,
                    window_seconds=60,
                    now=started_at + timedelta(seconds=attempt),
                )

    asyncio.run(exercise())
    asyncio.run(engine.dispose())


def test_blocks_request_over_limit(tmp_path) -> None:
    session_factory, engine = _build_session_factory(tmp_path)

    async def exercise() -> None:
        started_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        for attempt in range(5):
            async with session_factory() as db:
                await enforce_rate_limit(
                    db=db,
                    key="ip:1.2.3.4",
                    limit=5,
                    window_seconds=60,
                    now=started_at + timedelta(seconds=attempt),
                )

        async with session_factory() as db:
            with pytest.raises(HTTPException):
                await enforce_rate_limit(
                    db=db,
                    key="ip:1.2.3.4",
                    limit=5,
                    window_seconds=60,
                    now=started_at + timedelta(seconds=5),
                )

    asyncio.run(exercise())
    asyncio.run(engine.dispose())


def test_different_keys_are_independent(tmp_path) -> None:
    session_factory, engine = _build_session_factory(tmp_path)

    async def exercise() -> None:
        started_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        for attempt in range(5):
            async with session_factory() as db:
                await enforce_rate_limit(
                    db=db,
                    key="ip:1.1.1.1",
                    limit=5,
                    window_seconds=60,
                    now=started_at + timedelta(seconds=attempt),
                )

        async with session_factory() as db:
            await enforce_rate_limit(
                db=db,
                key="ip:2.2.2.2",
                limit=5,
                window_seconds=60,
                now=started_at + timedelta(seconds=5),
            )

    asyncio.run(exercise())
    asyncio.run(engine.dispose())


def test_limit_of_one(tmp_path) -> None:
    session_factory, engine = _build_session_factory(tmp_path)

    async def exercise() -> None:
        started_at = datetime(2026, 3, 1, tzinfo=timezone.utc)
        async with session_factory() as db:
            await enforce_rate_limit(
                db=db,
                key="ip:x",
                limit=1,
                window_seconds=60,
                now=started_at,
            )

        async with session_factory() as db:
            with pytest.raises(HTTPException):
                await enforce_rate_limit(
                    db=db,
                    key="ip:x",
                    limit=1,
                    window_seconds=60,
                    now=started_at + timedelta(seconds=1),
                )

    asyncio.run(exercise())
    asyncio.run(engine.dispose())


def test_expired_entries_do_not_count(tmp_path):
    factory, engine = _build_session_factory(tmp_path)
    async def exercise():
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        async with factory() as db:
            await enforce_rate_limit(db=db,key="old",limit=1,window_seconds=60,now=now-timedelta(seconds=61))
            await enforce_rate_limit(db=db,key="old",limit=1,window_seconds=60,now=now)
            with pytest.raises(HTTPException) as exc:
                await enforce_rate_limit(db=db,key="old",limit=1,window_seconds=60,now=now)
            assert exc.value.status_code == 429
    asyncio.run(exercise());asyncio.run(engine.dispose())


def test_store_bounded_after_expiry(tmp_path):
    factory, engine = _build_session_factory(tmp_path)
    async def exercise():
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        async with factory() as db:
            await enforce_rate_limit(db=db,key="old",limit=5,window_seconds=60,now=now-timedelta(seconds=61))
            await enforce_rate_limit(db=db,key="recent",limit=5,window_seconds=60,now=now)
            rows=(await db.execute(select(RateLimitCounter))).scalars().all()
            assert len(rows)==2  # Requests no longer sweep expired windows.
            await cleanup_expired_counters(db=db, now=now)
            await db.commit()
            rows=(await db.execute(select(RateLimitCounter))).scalars().all()
            assert len(rows)==1
            assert rows[0].expires_at > int(now.timestamp())
    asyncio.run(exercise());asyncio.run(engine.dispose())


def test_periodic_worker_prunes_expired_counters_only(tmp_path, monkeypatch):
    from app.workers import queue

    factory, engine = _build_session_factory(tmp_path)
    monkeypatch.setattr(queue, "async_session_factory", factory)
    monkeypatch.setattr(queue, "_RATE_LIMIT_CLEANUP_INTERVAL_SECONDS", 0.001)

    async def exercise():
        now = int(datetime.now(timezone.utc).timestamp())
        async with factory() as db:
            db.add_all([
                RateLimitCounter(key="expired", window_start=now-60, count=1, expires_at=now-1),
                RateLimitCounter(key="active", window_start=now, count=1, expires_at=now+60),
            ])
            await db.commit()
        completed = asyncio.Event()
        monkeypatch.setattr(queue.logger, "debug", lambda *_args, **_kwargs: completed.set())
        task = asyncio.create_task(queue._rate_limit_cleanup_loop())
        try:
            await asyncio.wait_for(completed.wait(), timeout=2)
        finally:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        async with factory() as db:
            rows = (await db.execute(select(RateLimitCounter))).scalars().all()
            assert [row.key for row in rows] == ["active"]
            assert rows[0].count == 1
        await engine.dispose()

    asyncio.run(exercise())


def test_atomic_counter_serializes_concurrent_limit_checks(tmp_path):
    factory, engine = _build_session_factory(tmp_path)
    async def exercise():
        now = datetime(2026, 3, 1, tzinfo=timezone.utc)
        async def attempt():
            async with factory() as db:
                try:
                    await enforce_rate_limit(db=db,key="race",limit=1,window_seconds=60,now=now)
                    return 200
                except HTTPException as exc:
                    return exc.status_code
        results=await asyncio.gather(*(attempt() for _ in range(10)))
        assert results.count(200)==1
        assert results.count(429)==9
    asyncio.run(exercise());asyncio.run(engine.dispose())
