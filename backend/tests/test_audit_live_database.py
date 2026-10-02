"""Disposable local Postgres: outage, recovery, pool exhaustion; no application DB touched."""
import asyncio
import os
import time
import socket
import subprocess
import sys
from pathlib import Path
import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

pytestmark=pytest.mark.skipif(os.getenv('PROMPTCODE_AUDIT_DOCKER')!='1',reason='Live local Docker audit opt-in required')


def test_live_database_outage_recovery_and_pool_exhaustion():
    import docker
    client=docker.from_env(timeout=10);container=None
    try:
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            host_port = reservation.getsockname()[1]
        container=client.containers.run('postgres:16.11-alpine3.23',detach=True,
            environment={'POSTGRES_PASSWORD':'test-only-database-password','POSTGRES_DB':'audit'},
            ports={'5432/tcp':('127.0.0.1',host_port)},
            tmpfs={'/var/lib/postgresql/data':'rw,nosuid,size=128m'},
            mem_limit='256m',nano_cpus=1000000000,pids_limit=64,
            labels={'promptcode.audit':'test-only'})
        def ready():
            deadline=time.monotonic()+30
            while time.monotonic()<deadline:
                if container.exec_run(['pg_isready','-h','127.0.0.1','-U','postgres']).exit_code==0: return
                time.sleep(.2)
            raise AssertionError('Disposable database failed to start')
        ready();container.reload()
        port=container.attrs['NetworkSettings']['Ports']['5432/tcp'][0]['HostPort']
        url=f'postgresql+asyncpg://postgres:test-only-database-password@127.0.0.1:{port}/audit'
        backend=Path(__file__).resolve().parents[1]
        migration=subprocess.run([sys.executable,'-m','alembic','-c',str(backend/'alembic.ini'),'upgrade','head'],
            cwd=backend,env=dict(os.environ,PROMPTCODE_DATABASE_URL=url,PROMPTCODE_DATABASE_SSL_REQUIRE='false'),
            timeout=30,capture_output=True)
        assert migration.returncode==0,migration.stderr.decode()[-2000:]
        async def exercise():
            engine=create_async_engine(url,pool_size=1,max_overflow=0,pool_timeout=.2,pool_pre_ping=True,connect_args={'ssl':False,'timeout':2,'command_timeout':2})
            try:
                async with engine.connect() as held:
                    assert (await held.execute(text('SELECT 1'))).scalar_one()==1
                    started=time.monotonic()
                    with pytest.raises(Exception):
                        async with engine.connect(): pass
                    assert time.monotonic()-started<1
                container.stop(timeout=2)
                started=time.monotonic()
                with pytest.raises(Exception):
                    async with engine.connect() as conn: await conn.execute(text('SELECT 1'))
                assert time.monotonic()-started<3
                container.start();ready()
                async with engine.connect() as conn: assert (await conn.execute(text('SELECT 1'))).scalar_one()==1
                # Exercise the production-dialect upsert with independent connections.
                from app.models.rate_limit_counter import RateLimitCounter
                from app.core.ratelimit import enforce_rate_limit
                from sqlalchemy.ext.asyncio import async_sessionmaker
                from fastapi import HTTPException
                from datetime import datetime, timezone
                counters=create_async_engine(url,pool_size=10,max_overflow=0,connect_args={'ssl':False,'timeout':2,'command_timeout':2})
                try:
                    async with counters.begin() as conn: await conn.run_sync(lambda sync: RateLimitCounter.__table__.create(sync,checkfirst=True))
                    sessions=async_sessionmaker(counters)
                    now=datetime(2026,10,2,12,0,1,tzinfo=timezone.utc)
                    async def hit(key):
                        async with sessions() as db:
                            try:
                                await enforce_rate_limit(db=db,key=key,limit=10,window_seconds=60,now=now)
                                return 1
                            except HTTPException as exc:
                                assert exc.status_code==429
                                return 0
                    assert sum(await asyncio.gather(*(hit('shared') for _ in range(30))))==10
                    assert sum(await asyncio.gather(*(hit(f'distinct-{i}') for i in range(30))))==30
                finally: await counters.dispose()
                # Mid-request DB query hangs are bounded too.
                started=time.monotonic()
                with pytest.raises(Exception):
                    async with engine.connect() as conn: await conn.execute(text('SELECT pg_sleep(10)'))
                assert time.monotonic()-started<3
                async with engine.connect() as conn: assert (await conn.execute(text('SELECT 1'))).scalar_one()==1
            finally: await engine.dispose()
        asyncio.run(exercise())
    finally:
        if container is not None: container.remove(force=True,v=True)
        client.close()
