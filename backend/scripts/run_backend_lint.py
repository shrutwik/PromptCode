"""Run backend lint with the same targets and rules used in CI.

Usage:
    cd backend && python -m scripts.run_backend_lint
    cd backend && python -m scripts.run_backend_lint --fix
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


_RUFF_TARGETS = ("app/", "tests/")
_RUFF_SELECT = "F,E9,I"


def _backend_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _command(extra_args: list[str] | None = None) -> list[str]:
    args = [
        sys.executable,
        "-m",
        "ruff",
        "check",
        *_RUFF_TARGETS,
        "--select",
        _RUFF_SELECT,
    ]
    if extra_args:
        args.extend(extra_args)
    return args


def main(argv: list[str] | None = None) -> int:
    result = subprocess.run(
        _command(list(argv or [])),
        cwd=_backend_root(),
        check=False,
    )
    return int(result.returncode)


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
