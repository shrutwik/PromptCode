from __future__ import annotations

from pathlib import Path
import time

import pytest

from scripts import run_with_migrations


def test_run_pending_migrations_uses_repo_alembic_ini(monkeypatch: pytest.MonkeyPatch):
    calls: list[tuple[str, str]] = []

    class FakeConfig:
        def __init__(self, path: str):
            self.config_file_name = path

    def fake_upgrade(config, revision: str) -> None:
        calls.append((config.config_file_name, revision))

    monkeypatch.setattr(run_with_migrations, "Config", FakeConfig)
    monkeypatch.setattr(run_with_migrations.command, "upgrade", fake_upgrade)

    run_with_migrations.run_pending_migrations()

    expected = Path(__file__).resolve().parents[1] / "alembic.ini"
    assert calls == [(str(expected), "head")]


def test_main_runs_migrations_before_exec(monkeypatch: pytest.MonkeyPatch):
    events: list[tuple[str, list[str] | None]] = []

    def fake_run_pending_migrations() -> None:
        events.append(("migrate", None))

    def fake_exec_target(argv: list[str]) -> None:
        events.append(("exec", argv))

    monkeypatch.setattr(run_with_migrations, "run_pending_migrations", fake_run_pending_migrations)
    monkeypatch.setattr(run_with_migrations, "exec_target", fake_exec_target)

    run_with_migrations.main(["uvicorn", "app.main:app", "--port", "8000"])

    assert events == [
        ("migrate", None),
        ("exec", ["uvicorn", "app.main:app", "--port", "8000"]),
    ]


def test_main_requires_target_command():
    with pytest.raises(SystemExit) as exc_info:
        run_with_migrations.main([])

    assert "run_with_migrations <command>" in str(exc_info.value)


def test_run_pending_migrations_retries_alembic_version_race(
    monkeypatch: pytest.MonkeyPatch,
):
    calls: list[str] = []
    sleeps: list[float] = []

    class FakeConfig:
        def __init__(self, path: str):
            self.config_file_name = path

    def fake_upgrade(config, revision: str) -> None:
        calls.append(revision)
        if len(calls) == 1:
            raise RuntimeError(
                'duplicate key value violates unique constraint "pg_type_typname_nsp_index" '
                'while creating alembic_version'
            )

    monkeypatch.setattr(run_with_migrations, "Config", FakeConfig)
    monkeypatch.setattr(run_with_migrations.command, "upgrade", fake_upgrade)
    monkeypatch.setattr(time, "sleep", lambda seconds: sleeps.append(seconds))

    run_with_migrations.run_pending_migrations()

    assert calls == ["head", "head"]
    assert sleeps == [run_with_migrations._MIGRATION_RETRY_DELAY_SECONDS]


def test_run_pending_migrations_does_not_retry_non_retryable_error(
    monkeypatch: pytest.MonkeyPatch,
):
    class FakeConfig:
        def __init__(self, path: str):
            self.config_file_name = path

    def fake_upgrade(config, revision: str) -> None:
        raise RuntimeError("permission denied for relation leaderboard")

    monkeypatch.setattr(run_with_migrations, "Config", FakeConfig)
    monkeypatch.setattr(run_with_migrations.command, "upgrade", fake_upgrade)

    with pytest.raises(RuntimeError) as exc_info:
        run_with_migrations.run_pending_migrations()

    assert "permission denied" in str(exc_info.value)
