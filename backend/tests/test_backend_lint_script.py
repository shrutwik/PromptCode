from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts import run_backend_lint


def test_main_runs_ruff_with_ci_targets(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], Path, bool]] = []

    def fake_run(cmd: list[str], cwd: Path, check: bool) -> SimpleNamespace:
        calls.append((cmd, cwd, check))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run_backend_lint.subprocess, "run", fake_run)

    result = run_backend_lint.main()

    assert result == 0
    assert calls == [
        (
            [
                sys.executable,
                "-m",
                "ruff",
                "check",
                "app/",
                "tests/",
                "--select",
                "F,E9,I",
            ],
            Path(__file__).resolve().parents[1],
            False,
        )
    ]


def test_main_appends_extra_args(monkeypatch: pytest.MonkeyPatch) -> None:
    command: list[str] = []

    def fake_run(cmd: list[str], cwd: Path, check: bool) -> SimpleNamespace:
        del cwd, check
        command[:] = cmd
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(run_backend_lint.subprocess, "run", fake_run)

    result = run_backend_lint.main(["--fix"])

    assert result == 1
    assert command[-1] == "--fix"
