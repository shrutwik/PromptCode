"""Request-scoped database timings; never record SQL or parameter values."""
from __future__ import annotations

import time
from contextvars import ContextVar, Token
from typing import Any, Awaitable, Callable

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession

_timings: ContextVar[dict[str, float] | None] = ContextVar("database_timings", default=None)


def start_database_timing() -> tuple[Token[dict[str, float] | None], dict[str, float]]:
    values: dict[str, float] = {"db_ms": 0.0, "db_commit_ms": 0.0, "db_sql_ms": 0.0,
              "db_calls": 0, "db_statements": 0}
    return _timings.set(values), values


def reset_database_timing(token: Token[dict[str, float] | None]) -> None:
    _timings.reset(token)


async def _timed(method: Callable[..., Awaitable[Any]], *args: Any, commit: bool = False, **kwargs: Any) -> Any:
    values = _timings.get()
    if values is None:
        return await method(*args, **kwargs)
    started = time.perf_counter()
    try:
        return await method(*args, **kwargs)
    finally:
        elapsed = (time.perf_counter() - started) * 1000
        values["db_ms"] += elapsed
        values["db_calls"] += 1
        if commit:
            values["db_commit_ms"] += elapsed


class TimedAsyncSession(AsyncSession):
    async def execute(self, *args: Any, **kwargs: Any) -> Any:
        return await _timed(super().execute, *args, **kwargs)

    async def get(self, *args: Any, **kwargs: Any) -> Any:
        return await _timed(super().get, *args, **kwargs)

    async def commit(self) -> None:
        await _timed(super().commit, commit=True)

    async def flush(self, *args: Any, **kwargs: Any) -> None:
        await _timed(super().flush, *args, **kwargs)


def install_query_timing(engine: Any) -> None:
    def before(_conn: Any, _cursor: Any, _statement: Any, _parameters: Any, context: Any, _many: Any) -> None:
        if _timings.get() is not None:
            context._pc_query_started = time.perf_counter()

    def after(_conn: Any, _cursor: Any, _statement: Any, _parameters: Any, context: Any, _many: Any) -> None:
        values = _timings.get()
        started = getattr(context, "_pc_query_started", None)
        if values is not None and started is not None:
            values["db_sql_ms"] += (time.perf_counter() - started) * 1000
            values["db_statements"] += 1

    event.listen(engine.sync_engine, "before_cursor_execute", before)
    event.listen(engine.sync_engine, "after_cursor_execute", after)
