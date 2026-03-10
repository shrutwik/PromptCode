import asyncio
import ssl
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool

from app.core.config import get_settings
from app.db.alembic_compare import compare_type, should_include_object
from app.db.base import Base
import app.models  # noqa: F401 — ensure all models are imported

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

settings = get_settings()
# Alembic's ConfigParser treats '%' as interpolation markers; escape them.
_db_url = settings.database_url.replace("%", "%%")
config.set_main_option("sqlalchemy.url", _db_url)
_db_connect_args = {}
if settings.database_url.startswith("postgresql+"):
    if getattr(settings, "database_ssl_require", False):
        if getattr(settings, "database_ssl_ca_file", ""):
            _db_connect_args["ssl"] = ssl.create_default_context(
                cafile=settings.database_ssl_ca_file
            )
        else:
            _db_connect_args["ssl"] = ssl.create_default_context()
    # See app.db.session: disable asyncpg statement cache when going through
    # Supabase poolers to avoid prepared statement / connection issues.
    _db_connect_args["statement_cache_size"] = 0


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=compare_type,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=compare_type,
        include_object=lambda object_, name, type_, reflected, compare_to: should_include_object(
            connection.dialect.name, object_, name, type_, reflected, compare_to
        ),
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    from sqlalchemy.ext.asyncio import create_async_engine
    connectable = create_async_engine(
        settings.database_url,
        poolclass=pool.NullPool,
        connect_args=_db_connect_args,
    )
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
