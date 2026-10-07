"""Tests for the Modal execution backend.

The Modal SDK is not a test dependency (the execution host installs it, the test
host must not need it), so a fake ``modal`` module is injected through
``sys.modules`` exactly where the backend's lazy ``import modal`` resolves. This
mirrors how other suites in this repo stub external services.
"""
from __future__ import annotations

import sys
import threading
import types
from pathlib import Path
from typing import Any

import pytest

from app.core.config import get_settings
from app.services.execution import backend as backend_module
from app.services.execution import modal_backend
from app.services.execution.modal_backend import (
    ChallengeRunOutcome,
    ModalSandboxBackend,
    SandboxUnavailable,
    modal_image_for,
)
from app.services.execution.policy import (
    MAX_CPU,
    MAX_MEMORY_MB,
    MAX_OUTPUT_LIMIT_BYTES,
    MAX_PIDS_LIMIT,
    MAX_TIMEOUT_SECONDS,
    MIN_CPU,
    MIN_MEMORY_MB,
    MIN_OUTPUT_LIMIT_BYTES,
    MIN_PIDS_LIMIT,
    MIN_TIMEOUT_SECONDS,
    SandboxPolicy,
    assert_no_secret_env,
    candidate_environment,
    is_secret_env_key,
)

NODE_IMAGE = "registry.example/runner-node:1"
PYTHON_IMAGE = "registry.example/runner-python:1"
SECRET_ENV = {
    "DEEPSEEK_API_KEY": "sk-deepseek-live",
    "OPENAI_API_KEY": "sk-openai-live",
    "PROMPTCODE_JWT_SECRET": "jwt-signing-secret",
    "PROMPTCODE_DATABASE_URL": "postgres://user:pass@db/app",
    "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN": "executor-bearer",
    "PROMPTCODE_SUPABASE_SERVICE_ROLE_KEY": "supabase-role-key",
    "MODAL_TOKEN_ID": "modal-token-id",
    "MODAL_TOKEN_SECRET": "modal-token-secret",
    "GRADING_SIGNING_KEY": "grading-key-32-bytes-minimum-value",
}


class _FakeTimeoutError(Exception):
    """Named like Modal's timeout errors so the backend classifies it as one."""


class _FakeStream:
    def __init__(self, data: bytes) -> None:
        self._data = bytearray(data)

    def __iter__(self):
        while self._data:
            chunk = bytes(self._data[:256])
            del self._data[:256]
            yield chunk


class _FakeProcess:
    def __init__(self, *, stdout: bytes = b"", stderr: bytes = b"", exit_code: int = 0,
                 wait_error: BaseException | None = None) -> None:
        self.stdout = _FakeStream(stdout)
        self.stderr = _FakeStream(stderr)
        self._exit_code = exit_code
        self._wait_error = wait_error

    def wait(self) -> int:
        if self._wait_error is not None:
            raise self._wait_error
        return self._exit_code


class _FakeFilesystem:
    def __init__(self) -> None:
        self.files: dict[str, bytes] = {}
        self.directories: set[str] = set()

    def make_directory(self, remote_path: str, *, create_parents: bool = True) -> None:
        self.directories.add(str(remote_path))

    def write_bytes(self, data: bytes, remote_path: str) -> None:
        self.files[str(remote_path)] = bytes(data)

    def read_bytes(self, remote_path: str) -> bytes:
        return self.files[str(remote_path)]


class _FakeSandbox:
    def __init__(self, *, process: _FakeProcess | None, exec_error: BaseException | None) -> None:
        self.filesystem = _FakeFilesystem()
        self.process = process
        self.exec_error = exec_error
        self.terminated = False
        self.terminate_calls = 0
        self.exec_argv: tuple[str, ...] | None = None
        self.exec_kwargs: dict[str, Any] | None = None

    def exec(self, *argv: str, **kwargs: Any) -> _FakeProcess:
        self.exec_argv = argv
        self.exec_kwargs = kwargs
        if self.exec_error is not None:
            raise self.exec_error
        assert self.process is not None
        return self.process

    def terminate(self, **kwargs: Any) -> None:
        self.terminated = True
        self.terminate_calls += 1


class _FakeModal(types.ModuleType):
    def __init__(self) -> None:
        super().__init__("modal")
        self.process: _FakeProcess | None = None
        self.exec_error: BaseException | None = None
        self.created: list[_FakeSandbox] = []
        self.create_args: tuple[str, ...] = ()
        self.create_kwargs: dict[str, Any] = {}
        self.images: list[str] = []
        self.app_name = ""
        self.app_kwargs: dict[str, Any] = {}
        self.App = types.SimpleNamespace(lookup=self._lookup)
        self.Image = types.SimpleNamespace(from_registry=self._from_registry)
        self.Sandbox = types.SimpleNamespace(create=self._create)

    def _lookup(self, name: str, **kwargs: Any) -> Any:
        self.app_name = name
        self.app_kwargs = kwargs
        return types.SimpleNamespace(name=name)

    def _from_registry(self, reference: str, **kwargs: Any) -> Any:
        self.images.append(str(reference))
        return types.SimpleNamespace(reference=reference)

    def _create(self, *args: Any, **kwargs: Any) -> _FakeSandbox:
        self.create_args = args
        self.create_kwargs = kwargs
        sandbox = _FakeSandbox(process=self.process, exec_error=self.exec_error)
        self.created.append(sandbox)
        return sandbox


@pytest.fixture
def modal_settings(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("PROMPTCODE_EXECUTION_BACKEND", "modal")
    monkeypatch.setenv("PROMPTCODE_MODAL_SANDBOX_IMAGE_NODE", NODE_IMAGE)
    monkeypatch.setenv("PROMPTCODE_MODAL_SANDBOX_IMAGE_PYTHON", PYTHON_IMAGE)
    get_settings.cache_clear()
    backend_module._modal_backend = None
    try:
        yield get_settings()
    finally:
        get_settings.cache_clear()
        backend_module._modal_backend = None


@pytest.fixture
def fake_modal(monkeypatch: pytest.MonkeyPatch) -> _FakeModal:
    module = _FakeModal()
    monkeypatch.setitem(sys.modules, "modal", module)
    return module


def _source(tmp_path: Path) -> Path:
    root = tmp_path / "source"
    root.mkdir(exist_ok=True)
    (root / "app.js").write_text("export const value = 1;\n")
    return root


def test_source_upload_prunes_dependencies_and_links_without_scanning_them(tmp_path, monkeypatch):
    root = _source(tmp_path)
    (root / "src" / "empty").mkdir(parents=True)
    (root / "src" / "main.js").write_text("const value = 1;\n")
    for name in modal_backend._IGNORED_TREE_NAMES:
        (root / name / "deep").mkdir(parents=True)
        (root / name / "deep" / "unused.js").write_text("not uploaded")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_text("never uploaded")
    (root / "linked-dir").symlink_to(outside, target_is_directory=True)
    (root / "linked-file").symlink_to(outside / "secret")
    original = modal_backend.os.scandir

    def scan(path):
        assert Path(path).name not in modal_backend._IGNORED_TREE_NAMES
        assert Path(path) != outside
        return original(path)

    monkeypatch.setattr(modal_backend.os, "scandir", scan)
    sandbox = types.SimpleNamespace(filesystem=_FakeFilesystem())
    modal_backend._upload_source(sandbox, root)
    assert sandbox.filesystem.files == {
        "/source/app.js": b"export const value = 1;\n",
        "/source/src/main.js": b"const value = 1;\n",
    }
    assert "/source/src/empty" in sandbox.filesystem.directories
    assert not any("linked" in path for path in sandbox.filesystem.directories)


@pytest.mark.parametrize("fail_upload", [False, True])
def test_sandbox_phase_timings_include_failures_and_cleanup(modal_settings, fake_modal, tmp_path, monkeypatch, caplog, fail_upload):
    fake_modal.process = _FakeProcess(stdout=b"done", exit_code=0)
    policy = SandboxPolicy(cpu=1, memory_mb=512, timeout_seconds=30,
                           pids_limit=64, output_limit_bytes=4096)
    clock = [0.0]
    monkeypatch.setattr(modal_backend.time, "monotonic", lambda: clock[0])
    create = fake_modal.Sandbox.create

    def timed_create(*args, **kwargs):
        clock[0] += 0.1
        sandbox = create(*args, **kwargs)
        terminate = sandbox.terminate

        def timed_terminate():
            clock[0] += 0.04
            terminate()

        sandbox.terminate = timed_terminate
        execute = sandbox.exec

        def timed_exec(*args, **kwargs):
            clock[0] += 0.3
            return execute(*args, **kwargs)

        sandbox.exec = timed_exec
        return sandbox

    upload = modal_backend._upload_source

    def timed_upload(*args):
        clock[0] += 0.2
        if fail_upload:
            raise OSError("upload failed")
        return upload(*args)

    fake_modal.Sandbox.create = timed_create
    monkeypatch.setattr(modal_backend, "_upload_source", timed_upload)
    with caplog.at_level("INFO", logger=modal_backend.__name__):
        if fail_upload:
            with pytest.raises(OSError):
                ModalSandboxBackend()._execute(source_dir=_source(tmp_path), argv=["node"], image="node", policy=policy)
        else:
            result = ModalSandboxBackend()._execute(source_dir=_source(tmp_path), argv=["node"], image="node", policy=policy)
            assert result == (0, b"done", b"")
    record = next(r for r in caplog.records if r.getMessage() == "sandbox.complete")
    assert record.create_ms == 100
    assert record.upload_ms == 200
    assert record.execute_ms == (0 if fail_upload else 300)
    assert record.cleanup_ms == 40
    assert record.outcome == ("failed" if fail_upload else "completed")
    assert record.failed_phase == ("upload" if fail_upload else None)
    assert fake_modal.created[0].terminated


# --- policy -----------------------------------------------------------------


def test_policy_clamps_every_resource_value():
    oversized = SandboxPolicy(
        cpu=999.0, memory_mb=10**9, timeout_seconds=10**9,
        pids_limit=10**9, output_limit_bytes=10**9,
    )
    assert oversized.cpu == MAX_CPU
    assert oversized.memory_mb == MAX_MEMORY_MB
    assert oversized.timeout_seconds == MAX_TIMEOUT_SECONDS
    assert oversized.pids_limit == MAX_PIDS_LIMIT
    assert oversized.output_limit_bytes == MAX_OUTPUT_LIMIT_BYTES

    undersized = SandboxPolicy(
        cpu=-5.0, memory_mb=1, timeout_seconds=0, pids_limit=1, output_limit_bytes=1,
    )
    assert undersized.cpu == MIN_CPU
    assert undersized.memory_mb == MIN_MEMORY_MB
    assert undersized.timeout_seconds == MIN_TIMEOUT_SECONDS
    assert undersized.pids_limit == MIN_PIDS_LIMIT
    assert undersized.output_limit_bytes == MIN_OUTPUT_LIMIT_BYTES


def test_block_network_is_always_true_and_cannot_be_disabled():
    assert SandboxPolicy(
        cpu=1.0, memory_mb=512, timeout_seconds=30, pids_limit=64, output_limit_bytes=4096,
    ).block_network is True
    with pytest.raises(ValueError, match="egress"):
        SandboxPolicy(
            cpu=1.0, memory_mb=512, timeout_seconds=30, pids_limit=64,
            output_limit_bytes=4096, block_network=False,
        )


def test_policy_environment_refuses_secret_shaped_keys():
    for name in SECRET_ENV:
        assert is_secret_env_key(name), name
    assert not is_secret_env_key("HOME")
    assert not is_secret_env_key("PYTEST_ADDOPTS")
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        SandboxPolicy(
            cpu=1.0, memory_mb=512, timeout_seconds=30, pids_limit=64,
            output_limit_bytes=4096, environment={"OPENAI_API_KEY": "sk-live"},
        )
    with pytest.raises(ValueError, match="PROMPTCODE_SUPABASE_SERVICE_ROLE_KEY"):
        assert_no_secret_env({"PROMPTCODE_SUPABASE_SERVICE_ROLE_KEY": "value"})


def test_policy_environment_is_immutable_and_allowlisted():
    policy = SandboxPolicy(
        cpu=1.0, memory_mb=512, timeout_seconds=30, pids_limit=64, output_limit_bytes=4096,
    )
    assert dict(policy.environment) == candidate_environment()
    with pytest.raises(TypeError):
        policy.environment["HOME"] = "/root"  # type: ignore[index]


# --- sandbox creation -------------------------------------------------------


def test_modal_sandbox_blocks_network_and_honours_policy(modal_settings, fake_modal, tmp_path):
    fake_modal.process = _FakeProcess(stdout=b"1 passed\n", exit_code=0)
    outcome = ModalSandboxBackend().run_challenge(
        source_dir=_source(tmp_path), argv=["npm", "test"], image="promptcode-runner-node:latest",
        timeout_seconds=10_000, memory_mb=10**9, cpu_limit=99.0, output_limit_bytes=10**9,
    )

    assert outcome.exit_code == 0 and outcome.timed_out is False
    # The image's default command exits immediately. Upload and exec need a
    # live sandbox, independent of the candidate command executed later.
    assert fake_modal.create_args == ("sleep", "infinity")
    kwargs = fake_modal.create_kwargs
    # Modal allows egress by default; the sandbox must always block it.
    assert kwargs["block_network"] is True
    assert kwargs["env"] == candidate_environment()
    # Caller values are clamped: the requested 10000 s / 99 CPU / 1e9 MiB never
    # reach Modal, and the sandbox lifetime is bounded by the configured ceiling.
    assert kwargs["timeout"] == int(modal_settings.modal_sandbox_timeout_seconds)
    assert kwargs["cpu"] == MAX_CPU
    assert kwargs["memory"] == MAX_MEMORY_MB
    assert kwargs["pids_limit"] == int(modal_settings.modal_sandbox_pids_limit)
    assert kwargs["workdir"] == "/workspace"
    assert fake_modal.app_name == modal_settings.modal_app_name
    # Docker image references are mapped onto the configured Modal image.
    assert fake_modal.images == [NODE_IMAGE]
    # The validated source tree lands at /source (the Docker read-only mount) so
    # the trusted-probe bootstrap and the advisory wrapper both find it.
    assert fake_modal.created[0].filesystem.files["/source/app.js"] == b"export const value = 1;\n"
    assert "/workspace" in fake_modal.created[0].filesystem.directories
    assert fake_modal.created[0].exec_argv == ("npm", "test")
    assert fake_modal.created[0].exec_kwargs["text"] is False


def test_secret_environment_cannot_reach_a_sandbox(modal_settings, fake_modal, tmp_path, monkeypatch):
    for name, value in SECRET_ENV.items():
        monkeypatch.setenv(name, value)
    fake_modal.process = _FakeProcess(stdout=b"ok\n", exit_code=0)

    ModalSandboxBackend().run_challenge(
        source_dir=_source(tmp_path), argv=["npm", "test"], image="promptcode-runner-node:latest",
        timeout_seconds=30, memory_mb=512, cpu_limit=1.0, output_limit_bytes=4096,
    )

    environment = fake_modal.create_kwargs["env"]
    assert not any(is_secret_env_key(key) for key in environment)
    assert not any(secret in str(value) for value in environment.values() for secret in SECRET_ENV.values())
    # The allowlist is fixed: no ambient host variable is ever forwarded.
    assert set(environment) == set(candidate_environment())


def test_missing_modal_package_fails_with_a_clear_error(modal_settings, monkeypatch, tmp_path):
    # ``None`` in sys.modules makes ``import modal`` raise ImportError.
    monkeypatch.setitem(sys.modules, "modal", None)
    with pytest.raises(SandboxUnavailable, match="modal"):
        ModalSandboxBackend().run_challenge(
            source_dir=_source(tmp_path), argv=["npm", "test"], image="promptcode-runner-node:latest",
            timeout_seconds=30, memory_mb=512, cpu_limit=1.0, output_limit_bytes=4096,
        )


# --- lifecycle: terminate on every path ------------------------------------


def test_sandbox_terminated_on_success(modal_settings, fake_modal, tmp_path):
    fake_modal.process = _FakeProcess(stdout=b"ok\n", exit_code=0)
    ModalSandboxBackend().run_challenge(
        source_dir=_source(tmp_path), argv=["npm", "test"], image="promptcode-runner-node:latest",
        timeout_seconds=30, memory_mb=512, cpu_limit=1.0, output_limit_bytes=4096,
    )
    assert fake_modal.created[0].terminated is True


def test_sandbox_terminated_on_exception(modal_settings, fake_modal, tmp_path):
    fake_modal.exec_error = RuntimeError("sandbox exec failed")
    with pytest.raises(RuntimeError, match="sandbox exec failed"):
        ModalSandboxBackend().run_challenge(
            source_dir=_source(tmp_path), argv=["npm", "test"], image="promptcode-runner-node:latest",
            timeout_seconds=30, memory_mb=512, cpu_limit=1.0, output_limit_bytes=4096,
        )
    assert fake_modal.created[0].terminated is True


def test_sandbox_terminated_on_timeout(modal_settings, fake_modal, tmp_path):
    fake_modal.process = _FakeProcess(wait_error=_FakeTimeoutError("deadline exceeded"))
    outcome = ModalSandboxBackend().run_challenge(
        source_dir=_source(tmp_path), argv=["npm", "test"], image="promptcode-runner-node:latest",
        timeout_seconds=30, memory_mb=512, cpu_limit=1.0, output_limit_bytes=4096,
    )
    assert outcome.timed_out is True
    assert outcome.exit_code == -1
    assert "Timed out" in outcome.output
    assert fake_modal.created[0].terminated is True


def test_probe_timeout_raises_for_the_caller_to_map(modal_settings, fake_modal, tmp_path):
    fake_modal.process = _FakeProcess(wait_error=TimeoutError("deadline exceeded"))
    with pytest.raises(modal_backend.SandboxTimeout):
        ModalSandboxBackend().run_probe(
            source_dir=_source(tmp_path), argv=["node", "-e", "1"], image="promptcode-runner-node:latest",
            timeout_seconds=12, output_limit_bytes=4096,
        )
    assert fake_modal.created[0].terminated is True


def test_abort_path_terminates_a_live_sandbox(modal_settings, fake_modal, tmp_path):
    started = threading.Event()
    release = threading.Event()

    class _BlockingProcess(_FakeProcess):
        def wait(self) -> int:
            started.set()
            release.wait(5)
            return 0

    fake_modal.process = _BlockingProcess()
    backend = ModalSandboxBackend()
    captured: dict[str, Any] = {}

    def run() -> None:
        try:
            captured["outcome"] = backend.run_challenge(
                source_dir=_source(tmp_path), argv=["npm", "test"], image="promptcode-runner-node:latest",
                timeout_seconds=30, memory_mb=512, cpu_limit=1.0, output_limit_bytes=4096,
            )
        except BaseException as exc:  # noqa: BLE001 - observed by the assertion below
            captured["error"] = exc

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert started.wait(5)
        backend.cancel()
        assert fake_modal.created[0].terminated is True
    finally:
        release.set()
        thread.join(5)
    assert thread.is_alive() is False


def test_abort_during_creation_still_terminates_the_sandbox(modal_settings, fake_modal, tmp_path):
    entered = threading.Event()
    release = threading.Event()
    original_create = fake_modal.Sandbox.create

    def blocking_create(*args: Any, **kwargs: Any) -> _FakeSandbox:
        sandbox = original_create(*args, **kwargs)
        entered.set()
        release.wait(5)
        return sandbox

    fake_modal.Sandbox.create = blocking_create
    fake_modal.process = _FakeProcess(exit_code=0)
    backend = ModalSandboxBackend()
    errors: list[BaseException] = []

    def run() -> None:
        try:
            backend.run_challenge(
                source_dir=_source(tmp_path), argv=["npm", "test"], image="promptcode-runner-node:latest",
                timeout_seconds=30, memory_mb=512, cpu_limit=1.0, output_limit_bytes=4096,
            )
        except BaseException as exc:  # noqa: BLE001 - observed by the assertion below
            errors.append(exc)

    thread = threading.Thread(target=run)
    thread.start()
    try:
        assert entered.wait(5)
        backend.cancel()
    finally:
        release.set()
        thread.join(5)
    assert fake_modal.created[0].terminated is True
    assert isinstance(errors[0], modal_backend.SandboxAborted)


# --- output truncation ------------------------------------------------------


def test_output_is_truncated_to_the_policy_limit(modal_settings, fake_modal, tmp_path):
    payload = b"a" * 4096
    fake_modal.process = _FakeProcess(stdout=payload, exit_code=0)
    exit_code, raw = ModalSandboxBackend().run_probe(
        source_dir=_source(tmp_path), argv=["node", "-e", "1"], image="promptcode-runner-node:latest",
        timeout_seconds=12, output_limit_bytes=1024,
    )
    assert exit_code == 0
    assert len(raw) == 1024
    assert raw == payload[-1024:]
    assert not fake_modal.process.stdout._data

    fake_modal.process = _FakeProcess(stdout=payload, stderr=payload, exit_code=0)
    outcome = ModalSandboxBackend().run_challenge(
        source_dir=_source(tmp_path), argv=["npm", "test"], image="promptcode-runner-node:latest",
        timeout_seconds=30, memory_mb=512, cpu_limit=1.0, output_limit_bytes=1024,
    )
    assert len(outcome.output) == 1024


# --- backend selection ------------------------------------------------------


def test_get_execution_backend_defaults_to_docker(monkeypatch):
    monkeypatch.delenv("PROMPTCODE_EXECUTION_BACKEND", raising=False)
    get_settings.cache_clear()
    try:
        backend = backend_module.get_execution_backend()
        assert isinstance(backend, backend_module.DockerExecutionBackend)
        assert backend.name == "docker"
    finally:
        get_settings.cache_clear()


def test_get_execution_backend_selects_modal(modal_settings):
    backend = backend_module.get_execution_backend()
    assert isinstance(backend, ModalSandboxBackend)
    assert backend.name == "modal"
    # A single instance is returned so the abort path can reach live sandboxes.
    assert backend_module.get_execution_backend() is backend


def test_pids_limit_is_only_passed_when_the_sdk_supports_it():
    def supports(*args: Any, pids_limit: int = 0) -> None:
        pass

    def does_not_support(*args: Any, cpu: float = 0) -> None:
        pass

    assert modal_backend._accepts_keyword(supports, "pids_limit") is True
    assert modal_backend._accepts_keyword(does_not_support, "pids_limit") is False
    assert modal_backend._accepts_keyword(lambda **kwargs: None, "pids_limit") is True


def test_modal_image_mapping_is_per_stack(modal_settings):
    assert modal_image_for("promptcode-runner-python:latest", ["pytest", "-q"]) == PYTHON_IMAGE
    assert modal_image_for("promptcode-runner-node:latest", ["npm", "test"]) == NODE_IMAGE
    assert modal_image_for("approved-python", ["sh", "/opt/run.sh"]) == PYTHON_IMAGE
    assert modal_image_for("", ["node", "-e", "1"]) == NODE_IMAGE


# --- in-sandbox layout and dependency layer ---------------------------------


def test_bootstrap_reproduces_the_docker_run_sh_layout():
    wrapped = modal_backend.bootstrap_argv(["pytest", "-q"], challenge_slug="order-hold-reason")
    assert wrapped[:2] == ["sh", "-c"]
    script = wrapped[2]
    assert "cp -R /source/. /workspace/" in script
    assert "/opt/promptcode-deps/$slug/node_modules" in script
    assert 'exec "$@"' in script
    # run.sh sleeps to keep its tmpfs alive for a post-exit read; reusing it here
    # would make every Modal run hit its deadline.
    assert "sleep" not in script
    assert wrapped[4] == "order-hold-reason"
    assert wrapped[5:] == ["pytest", "-q"]


def test_bootstrap_rejects_a_slug_that_could_escape_the_deps_path():
    with pytest.raises(ValueError):
        modal_backend.bootstrap_argv(["pytest", "-q"], challenge_slug="../../etc")
    # Non-registry callers may pass no slug: the dependency step is then skipped.
    assert modal_backend.bootstrap_argv(["pytest", "-q"], challenge_slug="")[4] == ""


def test_challenge_dependency_mounts_match_the_docker_deps_root(tmp_path, monkeypatch):
    from app.services.execution import images

    challenges = tmp_path / "challenges"
    for slug in ("invoice-status-transition", "order-hold-reason"):
        (challenges / slug / "node_modules").mkdir(parents=True)
    (challenges / "Bad Slug" / "node_modules").mkdir(parents=True)

    mounts = images.challenge_dependency_mounts(challenges)
    assert mounts == {
        str(challenges / "invoice-status-transition" / "node_modules"): (
            "/opt/promptcode-deps/invoice-status-transition/node_modules"
        ),
        str(challenges / "order-hold-reason" / "node_modules"): (
            "/opt/promptcode-deps/order-hold-reason/node_modules"
        ),
    }

    # A clean checkout has no installed node_modules. Exercise default-root
    # resolution with the same reviewed fixture rather than developer caches.
    monkeypatch.setattr(images, "DEFAULT_CHALLENGES_DIR", challenges)
    assert images.challenge_dependency_mounts() == mounts


def test_build_sandbox_image_adds_every_dependency_layer(tmp_path):
    from app.services.execution import images

    class _Image:
        def __init__(self, reference: str, added: list[tuple[str, str]] | None = None) -> None:
            self.reference = reference
            self.added = added or []

        def add_local_dir(self, local_dir: str, remote_dir: str) -> "_Image":
            return _Image(self.reference, [*self.added, (local_dir, remote_dir)])

    fake = types.SimpleNamespace(Image=types.SimpleNamespace(from_registry=_Image))
    challenges = tmp_path / "challenges"
    (challenges / "invoice-status-transition" / "node_modules").mkdir(parents=True)

    image = images.build_sandbox_image(
        fake, base_image="node:20.19-bookworm-slim", challenges_dir=challenges
    )
    assert image.reference == "node:20.19-bookworm-slim"
    assert image.added == [
        (
            str(challenges / "invoice-status-transition" / "node_modules"),
            "/opt/promptcode-deps/invoice-status-transition/node_modules",
        )
    ]


def test_runner_modal_path_wraps_argv_with_the_bootstrap(monkeypatch, tmp_path):
    from app.services.interview import runner as runner_module

    workspace = tmp_path / "session"
    workspace.mkdir()
    (workspace / "app.js").write_text("export const value = 1;\n")
    monkeypatch.setattr(
        "app.services.interview.workspace.workspace_has_escape_link", lambda _workspace: False
    )
    monkeypatch.setattr("app.services.interview.workspace_quota.usage", lambda _workspace: None)
    captured: dict[str, Any] = {}

    class _Backend:
        name = "modal"

        def run_challenge(self, **kwargs: Any) -> ChallengeRunOutcome:
            captured.update(kwargs)
            return ChallengeRunOutcome(exit_code=0, output="1 passed\n", duration_ms=3)

    result = runner_module.IsolatedRunner()._run_modal_with_slot(
        workspace, "npm test", 30, "run_tests",
        {"image": "promptcode-runner-node:latest", "challengeSlug": "invoice-status-transition"},
        _Backend(),
    )

    argv = captured["argv"]
    assert argv[:3] == ["sh", "-c", argv[2]]
    assert argv[4] == "invoice-status-transition"
    assert argv[5:] == ["npm", "test"]
    assert captured["source_dir"] == workspace.resolve()
    assert result["ok"] is True
    assert result["isolation"] == "modal" and result["runner"] == "modal"
    assert result["command"] == "npm test"


def test_challenge_outcome_keeps_the_docker_shape():
    outcome = ChallengeRunOutcome(exit_code=1, output="boom", duration_ms=5)
    assert (outcome.exit_code, outcome.output, outcome.duration_ms) == (1, "boom", 5)
    assert outcome.timed_out is False


# --- grading contract -------------------------------------------------------


def test_probe_taxonomy_is_unchanged_on_modal(modal_settings, fake_modal, tmp_path):
    from app.services.interview import trusted_evaluator as evaluator

    source = _source(tmp_path)
    expected_argv = evaluator._probe_command("invoice-status-transition", "result=1")

    def observe(process: _FakeProcess) -> tuple[object, str | None]:
        fake_modal.process = process
        return evaluator._run_probe(source, "invoice-status-transition", "result=1")

    assert observe(_FakeProcess(stdout=b'{"ok": true}', exit_code=0)) == ({"ok": True}, None)
    assert observe(_FakeProcess(stdout=b"nope", exit_code=3)) == (None, "candidate_error")
    assert observe(_FakeProcess(stdout=b"NaN", exit_code=0)) == (None, "invalid_output")
    assert observe(_FakeProcess(stdout=b"x" * (evaluator.MAX_OUTPUT_BYTES + 5), exit_code=0)) == (
        None,
        "invalid_output",
    )
    assert observe(_FakeProcess(wait_error=_FakeTimeoutError("deadline"))) == (None, "timeout")

    # The probe ran the allowlisted node argv in the node sandbox image, reading
    # the candidate tree from /source exactly like the Docker mount.
    assert fake_modal.created[-1].exec_argv == tuple(expected_argv)
    assert "/source/app.js" in fake_modal.created[-1].filesystem.files
    assert fake_modal.images[-1] == NODE_IMAGE
    assert all(sandbox.terminated for sandbox in fake_modal.created)
