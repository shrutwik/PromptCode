"""Run Alembic migrations, then exec the target command.

Usage:
    cd backend && python -m scripts.run_with_migrations uvicorn app.main:app --reload --port 8000
    cd backend && python -m scripts.run_with_migrations python -m scripts.run_queue_worker
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config


_MIGRATION_RETRY_ATTEMPTS = 5
_MIGRATION_RETRY_DELAY_SECONDS = 2.0


def _alembic_ini_path() -> Path:
    return Path(__file__).resolve().parents[1] / "alembic.ini"


def _is_retryable_migration_error(exc: Exception) -> bool:
    message = str(exc).lower()
    if "alembic_version" not in message:
        return False
    return ("already exists" in message) or ("duplicate key value" in message)


def run_pending_migrations() -> None:
    config = Config(str(_alembic_ini_path()))
    for attempt in range(1, _MIGRATION_RETRY_ATTEMPTS + 1):
        try:
            command.upgrade(config, "head")
            return
        except Exception as exc:
            if attempt >= _MIGRATION_RETRY_ATTEMPTS or not _is_retryable_migration_error(exc):
                raise
            time.sleep(_MIGRATION_RETRY_DELAY_SECONDS)


def exec_target(argv: list[str]) -> "NoReturn":
    os.execvp(argv[0], argv)


def main(argv: list[str] | None = None) -> None:
    args = list(sys.argv[1:] if argv is None else argv)
    if not args:
        raise SystemExit("Usage: python -m scripts.run_with_migrations <command> [args...]")
    run_pending_migrations()
    exec_target(args)


if __name__ == "__main__":
    main()
