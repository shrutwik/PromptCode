"""Run Alembic migrations, then exec the target command.

Usage:
    cd backend && python -m scripts.run_with_migrations uvicorn app.main:app --reload --port 8000
    cd backend && python -m scripts.run_with_migrations python -m scripts.run_queue_worker
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config


def _alembic_ini_path() -> Path:
    return Path(__file__).resolve().parents[1] / "alembic.ini"


def run_pending_migrations() -> None:
    config = Config(str(_alembic_ini_path()))
    command.upgrade(config, "head")


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
