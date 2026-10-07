"""Security checks for the interview test runner. No Docker daemon required."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

from app.services.interview.runner import (
    LocalDevelopmentRunner,
    _install_linux_node_modules,
    linux_npm_docker_argv,
    node_install_argv,
    restore_node_manifests,
    scrubbed_host_env,
)


def test_scrubbed_host_env_drops_secrets(monkeypatch):
    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "super-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    monkeypatch.setenv("PROMPTCODE_DATABASE_URL", "postgres://user:pass@db/app")
    monkeypatch.setenv("HOME", "/tmp/home")

    env = scrubbed_host_env()

    assert env["PATH"] == "/usr/bin"
    assert env["HOME"] == "/tmp/home"
    assert "PROMPTCODE_JWT_SECRET" not in env
    assert "OPENAI_API_KEY" not in env
    assert "PROMPTCODE_DATABASE_URL" not in env


def test_local_runner_does_not_pass_host_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTCODE_ALLOW_UNSAFE_LOCAL_RUNNER", "1")
    monkeypatch.setenv("PROMPTCODE_JWT_SECRET", "super-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
    ws = tmp_path / "sess"
    ws.mkdir()
    captured: dict = {}

    async def fake_exec(*_argv, **kwargs):
        captured["env"] = kwargs.get("env")

        class Proc:
            returncode = 0

            async def communicate(self):
                return b"1 passed\n", b""

        return Proc()

    monkeypatch.setattr(asyncio, "create_subprocess_exec", fake_exec)
    result = asyncio.run(LocalDevelopmentRunner().run_tests(ws, "pytest -q"))
    assert result["ok"] is False  # Host execution has no complete reporter evidence.
    assert result["authoritative"] is False
    assert "PROMPTCODE_JWT_SECRET" not in captured["env"]
    assert "OPENAI_API_KEY" not in captured["env"]
    assert captured["env"]["PYTHONPATH"] == str(ws)


def test_tampered_package_json_is_restored_before_install(tmp_path, monkeypatch):
    ws = tmp_path / "sess"
    starter = tmp_path / "sess.starter"
    ws.mkdir()
    starter.mkdir()
    trusted = '{"name":"challenge","scripts":{"test":"vitest"}}\n'
    (starter / "package.json").write_text(trusted, encoding="utf-8")
    (starter / "package-lock.json").write_text('{"lockfileVersion":3}\n', encoding="utf-8")
    (ws / "package.json").write_text(
        '{"scripts":{"preinstall":"echo pwned"}}\n',
        encoding="utf-8",
    )
    (ws / "package-lock.json").unlink(missing_ok=True)

    recorded: dict = {}

    def fake_run(argv, **_kwargs):
        recorded["argv"] = argv
        completed = MagicMock()
        completed.returncode = 0
        completed.stdout = ""
        completed.stderr = ""
        return completed

    monkeypatch.setattr(
        "app.services.interview.runner.subprocess.run",
        fake_run,
    )
    _install_linux_node_modules(ws, "promptcode-runner-node:latest")

    assert (ws / "package.json").read_text(encoding="utf-8") == trusted
    assert (ws / "package-lock.json").is_file()
    argv = recorded["argv"]
    assert "--ignore-scripts" in argv[-1].split()
    assert "--offline" in argv[-1].split()
    assert f"{ws}:/source:ro" in argv
    assert not (ws / "node_modules").exists()
    assert "--cap-drop" in argv
    assert "ALL" in argv
    assert "no-new-privileges" in argv
    assert argv.count("--network") == 1
    joined = " ".join(argv)
    assert "preinstall" not in joined


def test_node_install_without_starter_does_not_run_docker(tmp_path, monkeypatch):
    ws = tmp_path / "sess"
    ws.mkdir()
    (ws / "package.json").write_text('{"scripts":{"preinstall":"echo pwned"}}\n', encoding="utf-8")
    called = {"run": False}

    def fake_run(*_args, **_kwargs):
        called["run"] = True
        raise AssertionError("docker must not run")

    monkeypatch.setattr("app.services.interview.runner.subprocess.run", fake_run)
    _install_linux_node_modules(ws, "promptcode-runner-node:latest")
    assert called["run"] is False
    assert restore_node_manifests(ws) is False


def test_linux_npm_docker_argv_drops_capabilities(tmp_path):
    argv = linux_npm_docker_argv(tmp_path, "image:latest", node_install_argv(tmp_path))
    assert "--cap-drop" in argv
    assert "ALL" in argv
    assert "--read-only" in argv
    assert "docker.sock" not in " ".join(argv)
    assert node_install_argv(tmp_path)[1] == "install"
