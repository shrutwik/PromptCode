import ssl

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.config import get_settings

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
        pool_size=20,
        max_overflow=10,
        pool_pre_ping=True,
        connect_args=_connect_args,
    )

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncSession:  # type: ignore[misc]
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
