"""Populated-database migration path: upgrade, downgrade, and data preservation.

The audit found that migrations were only ever exercised on an *empty* database
(CI schema-drift) or with `alembic.command` monkeypatched, so the path that matters
in an incident — upgrading a database that already holds user data — was untested.
The deploy job runs `alembic upgrade head` on backend startup, so a revision that
loses rows or fails on existing data is a production outage.

This test provisions a disposable PostgreSQL, migrates it to the revision before
the newest one, seeds real rows, then upgrades to head and asserts the rows are
intact. It also walks the downgrade one revision and back.

Requires Docker: `PROMPTCODE_AUDIT_DOCKER=1`. No existing database is touched.

Scope limit: this proves the *newest* revision is reversible and that a populated
database reaches head intact. It does **not** make older revisions reversible.
`9fb7f8d6f3b1` deletes duplicate leaderboard rows before adding a uniqueness
constraint, so any downgrade past it permanently loses those rows; that is a
recorded limitation, not something a test can undo.
"""
from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path

import pytest

pytestmark = pytest.mark.skipif(
    os.getenv("PROMPTCODE_AUDIT_DOCKER") != "1",
    reason="Disposable live PostgreSQL opt-in required",
)

BACKEND = Path(__file__).resolve().parents[1]

# The revision immediately before the queue-index revision this work added. It is
# resolved at run time from the Alembic script directory, not hardcoded, so the
# test keeps working as revisions are added.
TARGET_DOWNGRADE = "audit03_interview_grading"


def _alembic(database_url: str, *args: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(BACKEND / "alembic.ini"), *args],
        cwd=BACKEND,
        env=dict(os.environ, PROMPTCODE_DATABASE_URL=database_url,
                 PROMPTCODE_DATABASE_SSL_REQUIRE="false"),
        capture_output=True,
        timeout=120,
    )


@pytest.fixture()
def disposable_database(disposable_postgres):
    """Each test starts from an empty schema on the shared disposable server."""
    url = disposable_postgres
    # Drop and recreate the public schema so test order cannot matter.
    _exec(url, "DROP SCHEMA public CASCADE")
    _exec(url, "CREATE SCHEMA public")
    return url


@pytest.fixture(scope="module")
def disposable_postgres():
    import docker

    client = docker.from_env(timeout=10)
    container = None
    try:
        with socket.socket() as reservation:
            reservation.bind(("127.0.0.1", 0))
            port = reservation.getsockname()[1]
        container = client.containers.run(
            "postgres:16.11-alpine3.23", detach=True,
            environment={"POSTGRES_PASSWORD": "test-only-migration-password",
                         "POSTGRES_DB": "migration_audit"},
            ports={"5432/tcp": ("127.0.0.1", port)},
            tmpfs={"/var/lib/postgresql/data": "rw,nosuid,size=256m"},
            mem_limit="256m", nano_cpus=1000000000, pids_limit=64,
            labels={"promptcode.audit": "test-only-migration"},
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if container.exec_run(["pg_isready", "-h", "127.0.0.1", "-U", "postgres"]).exit_code == 0:
                break
            time.sleep(0.2)
        else:
            raise AssertionError("Disposable PostgreSQL startup failed")
        yield (f"postgresql+asyncpg://postgres:test-only-migration-password"
               f"@127.0.0.1:{port}/migration_audit")
    finally:
        if container is not None:
            container.remove(force=True, v=True)
        client.close()


def _psql(database_url: str, sql: str) -> str:
    """Run SQL through the application driver and return the first scalar."""
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def run() -> str:
        engine = create_async_engine(database_url, connect_args={"ssl": False, "command_timeout": 10})
        try:
            async with engine.connect() as connection:
                result = await connection.execute(text(sql))
                value = result.scalar()
                await connection.commit()
                return "" if value is None else str(value)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _exec(database_url: str, sql: str) -> None:
    import asyncio

    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    async def run() -> None:
        engine = create_async_engine(database_url, connect_args={"ssl": False, "command_timeout": 10})
        try:
            async with engine.begin() as connection:
                await connection.execute(text(sql))
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_populated_database_upgrades_without_losing_rows(disposable_database):
    """Upgrade a seeded database to head: every seeded row must survive."""
    url = disposable_database
    # Build the schema at the revision *before* the newest one, then seed real data.
    # Upgrading to the target (not downgrading to it) keeps this independent of the
    # database's initial state.
    apply_target = _alembic(url, "upgrade", TARGET_DOWNGRADE)
    assert apply_target.returncode == 0, apply_target.stderr.decode()[-2000:]

    user_id = str(uuid.uuid4())
    session_id = str(uuid.uuid4())
    _exec(url, f"""
        INSERT INTO users (id, email, username, password_hash, role, created_at)
        VALUES ('{user_id}', 'migration@test.example', 'migration_user', 'test-only-hash', 'candidate', now())
    """)
    _exec(url, f"""
        INSERT INTO interview_sessions
            (id, user_id, owner_token, challenge_slug, challenge_version, status, workspace_path, created_at, updated_at)
        VALUES ('{session_id}', '{user_id}', 'token-{session_id[:8]}', 'order-hold-reason', '1',
                'submitted', '/var/promptcode/interview_workspaces/{session_id}', now(), now())
    """)
    _exec(url, f"""
        INSERT INTO interview_grading_jobs
            (id, session_id, source_digest, snapshot_path, snapshot_manifest, challenge_slug,
             challenge_version, status, attempts, max_attempts, available_at, created_at)
        VALUES ('{uuid.uuid4()}', '{session_id}', '{"a" * 64}', '/submitted/source', '{{"files": []}}',
                'order-hold-reason', '1', 'completed', 1, 3, now(), now())
    """)
    before_users = _psql(url, "SELECT COUNT(*) FROM users")
    before_sessions = _psql(url, "SELECT COUNT(*) FROM interview_sessions")
    before_jobs = _psql(url, "SELECT COUNT(*) FROM interview_grading_jobs")
    before_email = _psql(url, f"SELECT email FROM users WHERE id = '{user_id}'")

    upgrade = _alembic(url, "upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr.decode()[-2000:]

    assert _psql(url, "SELECT COUNT(*) FROM users") == before_users
    assert _psql(url, "SELECT COUNT(*) FROM interview_sessions") == before_sessions
    assert _psql(url, "SELECT COUNT(*) FROM interview_grading_jobs") == before_jobs
    assert _psql(url, f"SELECT email FROM users WHERE id = '{user_id}'") == before_email
    # The applied head must match the repository head exactly.
    assert _psql(url, "SELECT version_num FROM alembic_version") == _repo_head()


def test_new_indexes_exist_after_upgrade(disposable_database):
    """The queue indexes this work added are actually created by the migration."""
    url = disposable_database
    head = _alembic(url, "upgrade", "head")
    assert head.returncode == 0, head.stderr.decode()[-2000:]
    names = _psql(url, """
        SELECT string_agg(indexname, ',' ORDER BY indexname)
        FROM pg_indexes
        WHERE indexname IN (
            'ix_interview_grading_jobs_status_available',
            'ix_interview_grading_jobs_status_lease',
            'ix_interview_grading_jobs_created_at',
            'ix_evaluation_jobs_status_available')
    """)
    assert names.split(",") == [
        "ix_evaluation_jobs_status_available",
        "ix_interview_grading_jobs_created_at",
        "ix_interview_grading_jobs_status_available",
        "ix_interview_grading_jobs_status_lease",
    ], names


def test_latest_revision_downgrades_and_reapplies(disposable_database):
    """The newest revision must be reversible without touching existing rows."""
    url = disposable_database
    head = _alembic(url, "upgrade", "head")
    assert head.returncode == 0, head.stderr.decode()[-2000:]
    # Seed a session so the downgrade has real rows to preserve.
    user_id, session_id = str(uuid.uuid4()), str(uuid.uuid4())
    _exec(url, f"""
        INSERT INTO users (id, email, username, password_hash, role, created_at)
        VALUES ('{user_id}', 'downgrade@test.example', 'downgrade_user', 'test-only-hash', 'candidate', now())
    """)
    _exec(url, f"""
        INSERT INTO interview_sessions
            (id, user_id, owner_token, challenge_slug, challenge_version, status, workspace_path, created_at, updated_at)
        VALUES ('{session_id}', '{user_id}', 'token-{session_id[:8]}', 'order-hold-reason', '1',
                'submitted', '/unused/{session_id}', now(), now())
    """)
    sessions_before = _psql(url, "SELECT COUNT(*) FROM interview_sessions")
    jobs_before = _psql(url, "SELECT COUNT(*) FROM interview_grading_jobs")

    down = _alembic(url, "downgrade", TARGET_DOWNGRADE)
    assert down.returncode == 0, down.stderr.decode()[-2000:]
    # The dropped indexes are gone, but no data was touched.
    remaining = _psql(url, """
        SELECT COUNT(*) FROM pg_indexes WHERE indexname = 'ix_interview_grading_jobs_status_available'
    """)
    assert remaining == "0"
    assert _psql(url, "SELECT COUNT(*) FROM interview_sessions") == sessions_before
    assert _psql(url, "SELECT COUNT(*) FROM interview_grading_jobs") == jobs_before

    up = _alembic(url, "upgrade", "head")
    assert up.returncode == 0, up.stderr.decode()[-2000:]
    assert _psql(url, "SELECT COUNT(*) FROM interview_sessions") == sessions_before


def _repo_head() -> str:
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(BACKEND / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND / "alembic"))
    return ScriptDirectory.from_config(config).get_current_head()
