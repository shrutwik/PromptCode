import asyncio
from datetime import datetime,timezone,timedelta
import pytest
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine,async_sessionmaker
from app.models.rate_limit_counter import RateLimitCounter
from app.core.ratelimit import enforce_rate_limit


def test_atomic_shared_and_distinct_client_limits(tmp_path):
    async def run():
        engine=create_async_engine('sqlite+aiosqlite:///'+str(tmp_path/'limits.db'))
        async with engine.begin() as conn: await conn.run_sync(RateLimitCounter.__table__.create)
        factory=async_sessionmaker(engine)
        now=datetime(2026,10,2,12,0,1,tzinfo=timezone.utc)
        async def hit(key,limit=10):
            async with factory() as db:
                try: await enforce_rate_limit(db=db,key=key,limit=limit,window_seconds=60,now=now);return 1
                except HTTPException as exc: assert exc.status_code==429;return 0
        assert sum(await asyncio.gather(*(hit('shared') for _ in range(30))))==10
        assert sum(await asyncio.gather(*(hit(f'ip-{i}') for i in range(30))))==30
        # 30 normal classroom requests share one IP and fit the production IP budget.
        assert sum(await asyncio.gather(*(hit('classroom',120) for _ in range(30))))==30
        async with factory() as db:
            await enforce_rate_limit(db=db,key='shared',limit=10,window_seconds=60,now=now+timedelta(seconds=60))
            rows=(await db.execute(select(RateLimitCounter))).scalars().all()
            assert all('classroom' not in row.key and 'ip-' not in row.key for row in rows)
        await engine.dispose()
    asyncio.run(run())
