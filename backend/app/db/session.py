import ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings
from app.db.timing import TimedAsyncSession, install_query_timing

settings = get_settings()

_connect_args: dict = {}
if settings.database_url.startswith("postgresql+"):
    if settings.database_ssl_require:
        if settings.database_ssl_ca_file:
            _connect_args["ssl"] = ssl.create_default_context(
                cafile=settings.database_ssl_ca_file
            )
        else:
            _connect_args["ssl"] = ssl.create_default_context()
    # Supabase poolers (PgBouncer) don't support prepared statements in
    # transaction mode; disable asyncpg's statement cache to avoid issues.
    _connect_args["statement_cache_size"] = 0
    # Fail a new connection quickly when the host is down. Readiness checks
    # use the same bound so /ready does not sit on a multi-minute TCP timeout.
    _connect_args["timeout"] = settings.database_connect_timeout_seconds
    # A statement cap must exceed the pool wait, otherwise a transaction queued
    # behind the pool (or a row lock) is killed by the statement timeout before
    # pool_timeout can apply, surfacing as an unhandled 500.
    _connect_args["command_timeout"] = settings.database_command_timeout_seconds

if settings.database_url.startswith("sqlite+"):
    engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        connect_args=_connect_args,
    )
else:
    engine = create_async_engine(
        settings.database_url,
        echo=settings.database_echo,
        pool_size=settings.database_pool_size,
        # A simultaneous save burst waits behind the shared storage admission.
        # Keep connection counts bounded, but allow those transactions to finish.
        pool_timeout=settings.database_pool_timeout_seconds,
        max_overflow=settings.database_max_overflow,
        pool_pre_ping=True,
        pool_recycle=1800,  # recycle connections every 30 min; prevents silent drops by pgbouncer
        connect_args=_connect_args,
    )

install_query_timing(engine)

async_session_factory = async_sessionmaker(
    engine,
    class_=TimedAsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
