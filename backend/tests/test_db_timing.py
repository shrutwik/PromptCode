import asyncio

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.db.timing import (
    TimedAsyncSession,
    install_query_timing,
    reset_database_timing,
    start_database_timing,
)


def test_database_timings_cover_queries_and_commits_without_sql_values(tmp_path):
    async def exercise():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'timing.db'}")
        install_query_timing(engine)
        factory = async_sessionmaker(engine, class_=TimedAsyncSession)
        token, values = start_database_timing()
        try:
            async with factory() as db:
                assert (await db.execute(text("SELECT 42"))).scalar_one() == 42
                await db.commit()
            assert values["db_calls"] == 2
            assert values["db_statements"] == 1
            assert values["db_ms"] >= values["db_sql_ms"] > 0
            assert values["db_commit_ms"] > 0
            assert set(values) == {"db_calls", "db_statements", "db_ms", "db_sql_ms", "db_commit_ms"}
        finally:
            reset_database_timing(token)
            await engine.dispose()
    asyncio.run(exercise())


def test_database_timings_are_isolated_between_concurrent_requests(tmp_path):
    async def exercise():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'isolated.db'}")
        install_query_timing(engine)
        factory = async_sessionmaker(engine, class_=TimedAsyncSession)
        async def request(count):
            token, values = start_database_timing()
            try:
                async with factory() as db:
                    for _ in range(count):
                        await db.execute(text("SELECT 1"))
                return values
            finally:
                reset_database_timing(token)
        a, b = await asyncio.gather(request(1), request(3))
        assert a["db_statements"] == a["db_calls"] == 1
        assert b["db_statements"] == b["db_calls"] == 3
        await engine.dispose()
    asyncio.run(exercise())


def test_failed_database_calls_are_timed_and_exceptions_preserved(tmp_path):
    async def exercise():
        engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'error.db'}")
        factory = async_sessionmaker(engine, class_=TimedAsyncSession)
        token, values = start_database_timing()
        try:
            async with factory() as db:
                with pytest.raises(Exception, match="no such table"):
                    await db.execute(text("SELECT * FROM missing_table"))
            assert values["db_calls"] == 1
            assert values["db_ms"] > 0
        finally:
            reset_database_timing(token)
            await engine.dispose()
    asyncio.run(exercise())


def test_database_timings_reach_middleware_headers_and_logs(tmp_path, monkeypatch, caplog):
    import logging

    from fastapi import Depends
    from fastapi.testclient import TestClient
    from sqlalchemy.ext.asyncio import AsyncSession

    from app import main as main_module
    from app.core.config import get_settings
    from app.db import session as session_module

    engine = create_async_engine(f"sqlite+aiosqlite:///{tmp_path / 'middleware.db'}")
    install_query_timing(engine)
    factory = async_sessionmaker(engine, class_=TimedAsyncSession)
    monkeypatch.setattr(main_module, "engine", engine)
    monkeypatch.setattr(session_module, "async_session_factory", factory)
    get_settings.cache_clear()
    app = main_module.create_app()

    @app.get("/timing-probe")
    async def probe(db: AsyncSession = Depends(session_module.get_db)):
        await db.execute(text("SELECT 1"))
        await db.commit()
        return {"ok": True}

    with caplog.at_level(logging.INFO, logger="app.access"):
        with TestClient(app) as client:
            response = client.get("/timing-probe")
    assert response.status_code == 200
    record = next(r for r in caplog.records if r.name == "app.access" and r.path == "/timing-probe")
    assert record.db_calls == 2
    assert record.db_statements == 1
    assert record.db_ms > 0
    assert "sql;dur=" in response.headers["Server-Timing"]
    get_settings.cache_clear()
    asyncio.run(engine.dispose())
