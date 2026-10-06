"""Challenge test execution — allowlisted commands only; no raw shell from clients."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import shutil
import subprocess
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

from app.services.interview.execution_feedback import complete_report, read_report

logger = logging.getLogger(__name__)

# Exact allowlisted command templates. User input cannot invent shell strings.
ALLOWED_COMMANDS: dict[str, list[str]] = {
    "npm test": ["npm", "test"],
    "npm test -- --run": ["npm", "test", "--", "--run"],
    "npx vitest run": ["npx", "vitest", "run"],
    "pytest -q": ["pytest", "-q"],
    "pytest": ["pytest", "-q"],
    "python -m pytest -q": ["python", "-m", "pytest", "-q"],
}

# Browser / API send commandId only — never arbitrary argv.
COMMAND_IDS: frozenset[str] = frozenset(
    {"run_tests", "run_targeted_tests", "run_benchmark"}
)

DEFAULT_OUTPUT_LIMIT = 20_000
DEFAULT_TIMEOUT_SECONDS = 60
DEFAULT_MEMORY_MB = 768
DEFAULT_CPU_LIMIT = 1.5
DEFAULT_PIDS_LIMIT = 128
WORKSPACE_MOUNT = "/workspace"

# Stack → default runner image (deps prebuilt into image; no install during runs).
DEFAULT_IMAGES = {
    "node": "promptcode-runner-node:latest",
    "python": "promptcode-runner-python:latest",
}

_runner_semaphore: asyncio.Semaphore | None = None
_runner_waiters = 0


def _get_runner_semaphore() -> asyncio.Semaphore:
    global _runner_semaphore
    if _runner_semaphore is None:
        from app.core.config import get_settings

        _runner_semaphore = asyncio.Semaphore(max(1, int(get_settings().max_runners)))
    return _runner_semaphore


def resolve_command(command: str) -> list[str]:
    normalized = " ".join(command.strip().split())
    if normalized not in ALLOWED_COMMANDS:
        raise ValueError(
            f"Command not allowlisted: {command!r}. "
            f"Allowed: {sorted(ALLOWED_COMMANDS)}"
        )
    return list(ALLOWED_COMMANDS[normalized])


def resolve_command_id(
    command_id: str,
    challenge_test_command: str,
    commands_map: dict[str, str] | None = None,
) -> str:
    """Map a client commandId to an allowlisted challenge command string."""
    cid = (command_id or "run_tests").strip()
    if cid not in COMMAND_IDS:
        raise ValueError(f"Unknown commandId: {command_id!r}")
    if commands_map and cid in commands_map:
        cmd = str(commands_map[cid]).strip()
        resolve_command(cmd)  # validate allowlist
        return cmd
    return challenge_test_command


def local_runner_allowed() -> bool:
    """Host execution is opt-in. Untrusted candidate code must use Docker."""
    return os.getenv("PROMPTCODE_ALLOW_UNSAFE_LOCAL_RUNNER", "").strip() == "1"


def candidate_module_env(root: str) -> dict[str, str]:
    """Point Python and Node at the session tree only. root is the process cwd."""
    root = (root or "").rstrip("/") or "/"
    opts = " ".join(
        [
            "--rootdir",
            shlex.quote(root),
            "--confcutdir",
            shlex.quote(root),
            "--import-mode=prepend",
        ]
    )
    return {
        "PYTHONPATH": root,
        "NODE_PATH": root,
        "PYTEST_ADDOPTS": opts,
    }


_HOST_ENV_ALLOWLIST = frozenset(
    {
        "PATH",
        "HOME",
        "LANG",
        "LC_ALL",
        "LC_CTYPE",
        "TMPDIR",
        "TEMP",
        "TMP",
        "USER",
        "LOGNAME",
        "SHELL",
    }
)
_SECRET_ENV_NAME = re.compile(
    r"(KEY|SECRET|TOKEN|PASSWORD|PASSWD|DSN|DATABASE|CREDENTIAL|PRIVATE)",
    re.IGNORECASE,
)


def scrubbed_host_env() -> dict[str, str]:
    """Environment for the opt-in host runner. Never inherit API keys or DB URLs."""
    return {
        key: value
        for key, value in os.environ.items()
        if key in _HOST_ENV_ALLOWLIST and not _SECRET_ENV_NAME.search(key)
    }


def runner_mode() -> str:
    """Resolved runner mode: local | docker. Prefers PROMPTCODE_RUNNER."""
    raw = (os.getenv("PROMPTCODE_RUNNER") or os.getenv("INTERVIEW_RUNNER") or "").strip()
    if not raw:
        try:
            from app.core.config import get_settings

            raw = str(getattr(get_settings(), "runner", "") or "").strip()
        except Exception:
            raw = ""
    raw = raw.lower() or "local"
    if raw in {"docker", "isolated"}:
        return "docker"
    return "local"


def default_image_for_stack(stack: str | None) -> str:
    text = (stack or "").lower()
    if "python" in text:
        return DEFAULT_IMAGES["python"]
    return DEFAULT_IMAGES["node"]


def normalize_runner_config(
    meta: dict[str, Any] | None,
    *,
    fallback_test_command: str | None = None,
) -> dict[str, Any]:
    """Validate/normalize optional registry `runner` block with safe defaults."""
    meta = meta or {}
    block = meta.get("runner") if isinstance(meta.get("runner"), dict) else {}
    test_cmd = fallback_test_command or str(meta.get("test_command") or "npm test")
    commands = block.get("commands") if isinstance(block.get("commands"), dict) else {}
    normalized_commands: dict[str, str] = {}
    for cid in COMMAND_IDS:
        raw = commands.get(cid) or test_cmd
        cmd = " ".join(str(raw).strip().split())
        resolve_command(cmd)
        normalized_commands[cid] = cmd

    timeout = int(block.get("timeoutSeconds") or DEFAULT_TIMEOUT_SECONDS)
    timeout = max(5, min(timeout, 120))
    memory_mb = int(block.get("memoryMb") or DEFAULT_MEMORY_MB)
    memory_mb = max(256, min(memory_mb, 1024))
    cpu = float(block.get("cpuLimit") or DEFAULT_CPU_LIMIT)
    cpu = max(0.5, min(cpu, 2.0))
    image = str(block.get("image") or default_image_for_stack(meta.get("stack"))).strip()
    if not image or ".." in image or image.startswith("/") or "\\" in image:
        raise ValueError(f"Invalid runner image: {image!r}")

    return {
        "image": image,
        "commands": normalized_commands,
        "timeoutSeconds": timeout,
        "memoryMb": memory_mb,
        "cpuLimit": cpu,
        "pidsLimit": int(block.get("pidsLimit") or DEFAULT_PIDS_LIMIT),
        "network": "none",  # documented default: no outbound network
        "outputLimit": int(block.get("outputLimit") or DEFAULT_OUTPUT_LIMIT),
        "expectedTestIds": block.get("expectedTestIds") or [],
    }


class ChallengeRunner(ABC):
    """Abstract runner — app code must not shell-exec outside this interface."""

    @abstractmethod
    async def run_tests(
        self,
        workspace: Path,
        command: str,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        command_id: str = "run_tests",
        runner_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        ...

    async def run_targeted_tests(
        self,
        workspace: Path,
        command: str,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        command_id: str = "run_targeted_tests",
        runner_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = await self.run_tests(
            workspace,
            command,
            timeout_seconds=timeout_seconds,
            command_id=command_id,
            runner_config=runner_config,
        )
        result["mode"] = "targeted"
        return result

    async def run_benchmark(
        self,
        workspace: Path,
        command: str,
        *,
        timeout_seconds: int = 180,
        command_id: str = "run_benchmark",
        runner_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        result = await self.run_tests(
            workspace,
            command,
            timeout_seconds=timeout_seconds,
            command_id=command_id,
            runner_config=runner_config,
        )
        result["mode"] = "benchmark"
        return result


class LocalDevelopmentRunner(ChallengeRunner):
    """
    Host-cwd subprocess runner for local MVP.

    NOT production-safe: shares host FS/network/CPU with the app process.
    Prefer IsolatedRunner (Docker) for multi-tenant deployments.
    """

    async def run_tests(
        self,
        workspace: Path,
        command: str,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        command_id: str = "run_tests",
        runner_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        argv = resolve_command(command)
        started = time.monotonic()
        output_limit = int((runner_config or {}).get("outputLimit") or DEFAULT_OUTPUT_LIMIT)
        if not local_runner_allowed():
            return _result(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr="Test runner is not isolated. An administrator must enable the isolated runner.",
                command=shlex.join(argv),
                duration_ms=0,
                mode="full",
                isolation="host",
                command_id=command_id,
                runner="local",
                error_code="unsafe_runner",
            )
        from app.services.interview.workspace import workspace_has_escape_link

        if workspace_has_escape_link(workspace):
            return _result(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr="Workspace contains a link and was not executed.",
                command=shlex.join(argv),
                duration_ms=0,
                mode="full",
                isolation="host",
                command_id=command_id,
                runner="local",
                error_code="workspace_link",
            )
        try:
            root = str(workspace)
            child_env = scrubbed_host_env()
            child_env.update(candidate_module_env(root))
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=root,
                env=child_env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_b, stderr_b = await asyncio.wait_for(
                    proc.communicate(), timeout=timeout_seconds
                )
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                return _result(
                    ok=False,
                    exit_code=-1,
                    stdout="",
                    stderr=f"Timed out after {timeout_seconds}s",
                    command=shlex.join(argv),
                    duration_ms=int((time.monotonic() - started) * 1000),
                    mode="full",
                    isolation="host",
                    timed_out=True,
                    command_id=command_id,
                    runner="local",
                )
            stdout = _clip(stdout_b.decode("utf-8", errors="replace"), output_limit)
            stderr = _clip(stderr_b.decode("utf-8", errors="replace"), output_limit)
            counts = _parse_test_counts(stdout + "\n" + stderr)
            return _result(
                ok=False,
                exit_code=proc.returncode or 0,
                stdout=stdout,
                stderr=stderr,
                command=shlex.join(argv),
                duration_ms=int((time.monotonic() - started) * 1000),
                mode="full",
                counts=counts,
                isolation="host",
                command_id=command_id,
                runner="local",
            )
        except FileNotFoundError as exc:
            return _result(
                ok=False,
                exit_code=127,
                stdout="",
                stderr=f"Executable missing: {exc}",
                command=shlex.join(argv),
                duration_ms=int((time.monotonic() - started) * 1000),
                mode="full",
                isolation="host",
                command_id=command_id,
                runner="local",
            )


def _docker_client():
    """Lazy Docker client factory (patchable in unit tests)."""
    import docker

    return docker.from_env(timeout=10)


def reap_expired_runners() -> int:
    """Remove expired execution leases only; never touch unrelated Docker resources."""
    client = _docker_client()
    removed = 0
    try:
        containers = client.containers.list(all=True, filters={"label": [
            "promptcode.role=interview-runner",
            "promptcode.expires_at",
        ]})
        for container in containers:
            try:
                expires = float(container.labels.get("promptcode.expires_at", ""))
                if not (0 < expires <= time.time()):
                    continue
                container.remove(force=True, v=True)
                removed += 1
            except (ValueError, TypeError):
                continue
        return removed
    finally:
        client.close()


def wait_for_execution(container, timeout_seconds):
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        try:
            marker = read_report(container, "/tmp/promptcode-exit.json")
            status = marker.get("exit_code")
            if type(status) is int:
                return {"StatusCode": status}
        except Exception:
            pass
        container.reload()
        if container.attrs["State"]["Running"] is False:
            return container.wait(timeout=1)
        time.sleep(.1)
    raise TimeoutError("Execution deadline exceeded")


def _docker_errors():
    from docker.errors import APIError, ImageNotFound

    return APIError, ImageNotFound


class IsolatedRunner(ChallengeRunner):
    """
    Docker ephemeral-container runner for production interview execution.

    Security invariants:
    - Mount only the session workspace (rw) at /workspace
    - No Docker socket, no host secrets, no other sessions
    - Network disabled (default); metadata/internal services unreachable
    - Allowlisted command argv only; resource + time limits enforced
    - Container always killed/removed after the run
    - Never silently falls back to host execution
    """

    async def run_tests(
        self,
        workspace: Path,
        command: str,
        *,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
        command_id: str = "run_tests",
        runner_config: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cfg = runner_config or {}
        timeout = int(cfg.get("timeoutSeconds") or timeout_seconds or DEFAULT_TIMEOUT_SECONDS)
        timeout = max(5, min(timeout, 120))
        from app.core.config import get_settings
        settings = get_settings()
        if getattr(settings, "execution_broker_url", ""):
            import httpx
            from .execution_transfer import bundle_source
            slug = cfg.get("challengeSlug")
            if not slug:
                raise ValueError("Registered challenge identity is required")
            bundle = await asyncio.to_thread(bundle_source, workspace)
            from app.core.execution_transport import broker_tls_context, broker_json_async
            async with httpx.AsyncClient(timeout=timeout + 15, trust_env=False, verify=broker_tls_context(settings)) as client:
                try:
                    result = await broker_json_async(client, "POST", settings.execution_broker_url.rstrip("/") + "/v1/interview/run",
                        max_bytes=128 * 1024,
                        headers={"Authorization": "Bearer " + settings.sandbox_executor_token},
                        json={"challenge_slug": slug, "command_id": command_id, "source": bundle.model_dump()})
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code == 503:
                        return self._busy_result(command, command_id)
                    raise
            if not isinstance(result, dict) or not {"ok", "exit_code", "stdout", "stderr", "command"} <= result.keys():
                raise RuntimeError("Invalid interview execution response")
            return result
        if settings.sandbox_executor_url:
            import httpx
            # Send only the server-owned session id and allowlisted command id.
            # The executor resolves its path, image and command from the database.
            async with httpx.AsyncClient(timeout=timeout + 15) as client:
                response = await client.post(
                    settings.sandbox_executor_url.rstrip("/") + "/v1/interview/run",
                    headers={"Authorization": "Bearer " + settings.sandbox_executor_token},
                    json={"session_id": str(uuid.UUID(workspace.name)), "command_id": command_id},
                )
            if response.status_code != 200:
                raise RuntimeError("Interview executor unavailable")
            result = response.json()
            if not isinstance(result, dict) or not {"ok", "exit_code", "stdout", "stderr", "command"} <= result.keys():
                raise RuntimeError("Invalid interview executor response")
            return result
        sem = _get_runner_semaphore()

        acquire_timeout = max(1, int(get_settings().max_runners_acquire_timeout_seconds))
        global _runner_waiters
        if _runner_waiters >= max(1, int(get_settings().max_runners)) * 2:
            return self._busy_result(command, command_id)
        _runner_waiters += 1
        try:
            await asyncio.wait_for(sem.acquire(), timeout=acquire_timeout)
        except TimeoutError:
            return self._busy_result(command, command_id)
        finally:
            _runner_waiters -= 1
        task = asyncio.create_task(asyncio.to_thread(
            self._run_docker_sync, workspace.resolve(), command, timeout, command_id, cfg,
        ))
        # Cancellation of the HTTP request must not free an active execution slot.
        task.add_done_callback(lambda _: sem.release())
        return await asyncio.shield(task)

    @staticmethod
    def _busy_result(command: str, command_id: str) -> dict[str, Any]:
        return _result(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr="Runner busy — too many concurrent test runs. Retry shortly.",
                command=command,
                duration_ms=0,
                mode="full",
                isolation="docker",
                timed_out=False,
                command_id=command_id,
                runner="docker",
                error_code="runner_busy",
            )

    def _run_docker_sync(
        self, workspace: Path, command: str, timeout_seconds: int,
        command_id: str, runner_config: dict[str, Any],
    ) -> dict[str, Any]:
        from app.services.runner_capacity import execution_slot, RunnerBusy
        try:
            with execution_slot():
                from app.services.execution.backend import get_execution_backend

                backend = get_execution_backend()
                if backend.name == "modal":
                    return self._run_modal_with_slot(
                        workspace, command, timeout_seconds, command_id, runner_config, backend,
                    )
                return self._run_docker_with_slot(workspace, command, timeout_seconds, command_id, runner_config)
        except RunnerBusy:
            return self._busy_result(command, command_id)

    def _run_modal_with_slot(
        self,
        workspace: Path,
        command: str,
        timeout_seconds: int,
        command_id: str,
        runner_config: dict[str, Any],
        backend: Any,
    ) -> dict[str, Any]:
        """Advisory candidate run inside a Modal Sandbox.

        Applies the same allowlisted argv, workspace validation and result shape
        as the Docker path. The Docker reporter wrapper is intentionally not used:
        the Modal image is operator-supplied and the sandbox outcome carries no
        reporter inventory, so ``ok`` reflects the process exit code only. These
        results remain advisory (``authoritative`` is always False).
        """
        argv = resolve_command(command)
        # Mirror the Docker runner's run.sh layout (candidate tree at /source, a
        # writable copy at /workspace, reviewed per-challenge deps linked in).
        # run.sh itself cannot be reused: it sleeps to keep its tmpfs alive for a
        # post-exit report read, which would make every Modal run time out.
        from app.services.execution.modal_backend import bootstrap_argv

        sandbox_argv = bootstrap_argv(
            argv, challenge_slug=str(runner_config.get("challengeSlug") or "")
        )
        image = str(runner_config.get("image") or DEFAULT_IMAGES["node"])
        memory_mb = int(runner_config.get("memoryMb") or DEFAULT_MEMORY_MB)
        cpu = float(runner_config.get("cpuLimit") or DEFAULT_CPU_LIMIT)
        output_limit = int(runner_config.get("outputLimit") or DEFAULT_OUTPUT_LIMIT)
        started = time.monotonic()

        if not workspace.is_dir():
            return _result(
                ok=False, exit_code=-1, stdout="", stderr="Session workspace missing",
                command=shlex.join(argv), duration_ms=int((time.monotonic() - started) * 1000),
                mode="full", isolation="modal", command_id=command_id, runner="modal",
                error_code="workspace_missing",
            )

        from app.services.interview.workspace import workspace_has_escape_link

        if workspace_has_escape_link(workspace):
            return _result(
                ok=False, exit_code=-1, stdout="", stderr="Workspace contains a link and was not executed.",
                command=shlex.join(argv), duration_ms=int((time.monotonic() - started) * 1000),
                mode="full", isolation="modal", command_id=command_id, runner="modal",
                error_code="workspace_link",
            )

        from app.services.interview.workspace_quota import usage

        try:
            usage(workspace)
        except ValueError:
            return _result(
                ok=False, exit_code=-1, stdout="", stderr="Session workspace quota exceeded.",
                command=shlex.join(argv), duration_ms=int((time.monotonic() - started) * 1000),
                mode="full", isolation="modal", command_id=command_id, runner="modal",
                error_code="workspace_quota",
            )

        try:
            outcome = backend.run_challenge(
                source_dir=workspace.resolve(), argv=sandbox_argv, image=image,
                timeout_seconds=timeout_seconds, memory_mb=memory_mb, cpu_limit=cpu,
                output_limit_bytes=output_limit,
            )
        except Exception:  # noqa: BLE001 — never fall back to host execution
            logger.exception("Unexpected Modal interview runner error")
            return _result(
                ok=False, exit_code=-1, stdout="",
                stderr="Failed to start isolated Modal sandbox. Production runner cannot fall back to host.",
                command=shlex.join(argv), duration_ms=int((time.monotonic() - started) * 1000),
                mode="full", isolation="modal", command_id=command_id, runner="modal",
                error_code="modal_unavailable",
            )

        timed_out = bool(outcome.timed_out)
        cleaned = _scrub_host_paths(outcome.output, workspace)
        if timed_out:
            exit_code = -1
            stdout = ""
            stderr = _clip(
                f"Timed out after {timeout_seconds}s" + (f"\n{cleaned}" if cleaned else ""),
                output_limit,
            )
        else:
            exit_code = int(outcome.exit_code)
            stdout = _clip(cleaned, output_limit)
            stderr = ""
        counts = _parse_test_counts(stdout + "\n" + stderr)
        return _result(
            ok=(not timed_out) and exit_code == 0,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            command=shlex.join(argv),
            duration_ms=int((time.monotonic() - started) * 1000),
            mode="full",
            counts=counts,
            isolation="modal",
            timed_out=timed_out,
            command_id=command_id,
            runner="modal",
        )

    def _run_docker_with_slot(
        self,
        workspace: Path,
        command: str,
        timeout_seconds: int,
        command_id: str,
        runner_config: dict[str, Any],
    ) -> dict[str, Any]:
        argv = resolve_command(command)
        image = str(runner_config.get("image") or DEFAULT_IMAGES["node"])
        memory_mb = int(runner_config.get("memoryMb") or DEFAULT_MEMORY_MB)
        cpu = float(runner_config.get("cpuLimit") or DEFAULT_CPU_LIMIT)
        pids = int(runner_config.get("pidsLimit") or DEFAULT_PIDS_LIMIT)
        output_limit = int(runner_config.get("outputLimit") or DEFAULT_OUTPUT_LIMIT)
        started = time.monotonic()
        container = None
        name = f"pc-interview-{uuid.uuid4().hex[:12]}"

        try:
            APIError, ImageNotFound = _docker_errors()
        except ImportError:
            return _result(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr="Docker SDK unavailable on server. Install docker package.",
                command=shlex.join(argv),
                duration_ms=int((time.monotonic() - started) * 1000),
                mode="full",
                isolation="docker",
                timed_out=False,
                command_id=command_id,
                runner="docker",
                error_code="docker_sdk_missing",
            )

        if not workspace.is_dir():
            return _result(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr="Session workspace missing",
                command=shlex.join(argv),
                duration_ms=int((time.monotonic() - started) * 1000),
                mode="full",
                isolation="docker",
                command_id=command_id,
                runner="docker",
                error_code="workspace_missing",
            )

        from app.services.interview.workspace import workspace_has_escape_link

        if workspace_has_escape_link(workspace):
            return _result(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr="Workspace contains a link and was not executed.",
                command=shlex.join(argv),
                duration_ms=int((time.monotonic() - started) * 1000),
                mode="full",
                isolation="docker",
                command_id=command_id,
                runner="docker",
                error_code="workspace_link",
            )

        from app.services.interview.workspace_quota import usage
        try:
            usage(workspace)
        except ValueError:
            return _result(ok=False, exit_code=-1, stdout="", stderr="Session workspace quota exceeded.",
                           command=shlex.join(argv), duration_ms=0, mode="full", isolation="docker",
                           error_code="workspace_quota")
        # No dependency installation/copy may write to the persistent host workspace.
        # Dependencies must be supplied by a reviewed Linux runner image or bounded source cache.

        try:
            client = _docker_client()
        except Exception:  # noqa: BLE001 — surface daemon errors cleanly
            logger.warning("Docker daemon unavailable for interview runner")
            return _result(
                ok=False,
                exit_code=-1,
                stdout="",
                stderr="Docker daemon unavailable. Production runner cannot fall back to host.",
                command=shlex.join(argv),
                duration_ms=int((time.monotonic() - started) * 1000),
                mode="full",
                isolation="docker",
                command_id=command_id,
                runner="docker",
                error_code="docker_unavailable",
            )

        expected_ids = runner_config.get("expectedTestIds") or []
        reported_argv = argv
        is_python = argv[0] in {"pytest", "python"}
        if is_python:
            reported_argv = argv + ["-p", "promptcode_audit_reporter"]
        run_kwargs: dict[str, Any] = {
            "image": image,
            "command": ["sh", "/opt/promptcode-reporters/run.sh", *reported_argv],
            "name": name,
            "working_dir": WORKSPACE_MOUNT,
            "volumes": {
                str(workspace): {"bind": "/source", "mode": "ro"},
            },
            "environment": {
                "HOME": "/tmp",
                "PC_CHALLENGE_SLUG": str(runner_config.get("challengeSlug") or ""),
                "npm_config_cache": "/tmp/npm-cache",
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                "PYTHONDONTWRITEBYTECODE": "1",
                # Block package installs and lifecycle scripts during candidate runs.
                "npm_config_offline": "true",
                "npm_config_ignore_scripts": "true",
                **candidate_module_env(WORKSPACE_MOUNT),
                "PYTHONPATH": "/opt/promptcode-reporters:/workspace",
            },
            "mem_limit": f"{memory_mb}m",
            "nano_cpus": int(cpu * 1e9),
            # Each candidate has only loopback; no host, database, or peer route.
            "network_mode": "none",
            "extra_hosts": {"localhost": "127.0.0.1"},
            "read_only": True,
            "tmpfs": {
                "/tmp": "rw,noexec,nosuid,size=64m",
                WORKSPACE_MOUNT: "rw,nosuid,nodev,size=256m,uid=10001,gid=10001,mode=0700",
            },
            "detach": True,
            "stdout": True,
            "stderr": True,
            "remove": False,
            "log_config": {
                "type": "local",
                "config": {"max-size": "1m", "max-file": "1", "compress": "false"},
            },
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges"],
            "pids_limit": pids,
            "labels": {
                "promptcode.role": "interview-runner",
                "promptcode.component": "interview",
                "promptcode.command_id": command_id,
                "promptcode.expires_at": str(time.time() + timeout_seconds + 30),
            },
            # Never mount docker.sock; never pass host secrets.
        }

        timed_out = False
        exit_code = -1
        stdout = ""
        stderr = ""
        report_ok = False
        try:
            container = client.containers.run(**run_kwargs)
            try:
                wait_result = wait_for_execution(container, timeout_seconds)
                exit_code = int(wait_result.get("StatusCode", 1))
            except Exception:
                timed_out = True
                try:
                    container.kill()
                except Exception:  # noqa: BLE001
                    pass
                exit_code = -1
                stderr = f"Timed out after {timeout_seconds}s"

            if not timed_out and exit_code == 0 and is_python:
                try:
                    report_ok = complete_report(read_report(container), expected_ids)
                except Exception:
                    report_ok = False
            try:
                logs = container.logs(stdout=True, stderr=True)
                raw = logs.decode("utf-8", errors="replace") if isinstance(logs, (bytes, bytearray)) else str(logs)
            except Exception:  # noqa: BLE001
                raw = ""
            cleaned = _scrub_host_paths(raw, workspace)
            if timed_out:
                stdout = ""
                stderr = _clip(stderr + ("\n" + cleaned if cleaned else ""), output_limit)
            else:
                # docker combines streams; split best-effort into stdout
                stdout = _clip(cleaned, output_limit)
                stderr = ""
        except ImageNotFound:
            stderr = f"Runner image not found: {image}. Build interview runner images before enabling docker mode."
            exit_code = -1
        except APIError as exc:
            logger.warning("Interview docker API error: %s", type(exc).__name__)
            stderr = "Failed to start isolated runner container."
            exit_code = -1
        except Exception:
            logger.exception("Unexpected interview docker error")
            stderr = "Unexpected isolated runner failure."
            exit_code = -1
        finally:
            if container is not None:
                try:
                    container.remove(force=True, v=True)
                except Exception:  # noqa: BLE001
                    try:
                        client.containers.get(name).remove(force=True, v=True)
                    except Exception:  # noqa: BLE001
                        logger.warning("Failed to remove interview container %s", name)

        counts = _parse_test_counts(stdout + "\n" + stderr)
        return _result(
            ok=(not timed_out) and exit_code == 0 and report_ok,
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            command=shlex.join(argv),
            duration_ms=int((time.monotonic() - started) * 1000),
            mode="full",
            counts=counts,
            error_code="incomplete_test_report" if exit_code == 0 and not report_ok else None,
            isolation="docker",
            timed_out=timed_out,
            command_id=command_id,
            runner="docker",
        )


def get_challenge_runner() -> ChallengeRunner:
    """Select the advisory runner for this deployment.

    ``PROMPTCODE_RUNNER=docker`` keeps the self-managed container path. On the
    managed stack (``PROMPTCODE_EXECUTION_BACKEND=modal``) the legacy runner stays
    at ``local`` by design and candidate code is forbidden from running on the API
    host, so the isolated runner is selected too: its dispatcher routes the
    allowlisted argv to the Modal execution backend. Without this, every advisory
    ``/tests`` run on the managed stack answered ``unsafe_runner`` and no sandbox
    was ever created.
    """
    mode = runner_mode()
    if mode == "docker":
        return IsolatedRunner()
    from app.core.config import get_settings

    if str(getattr(get_settings(), "execution_backend", "")).strip().lower() == "modal":
        return IsolatedRunner()
    return LocalDevelopmentRunner()


def docker_runner_health(*, probe_exec: bool = True) -> dict[str, Any]:
    """Admin/internal diagnostic for Docker interview runner readiness."""
    report: dict[str, Any] = {
        "runner_mode": runner_mode(),
        "docker": {"ok": False, "detail": ""},
        "images": {},
        "probe_exec": {"ok": False, "detail": "skipped"},
        "limits": {
            "default_timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
            "default_memory_mb": DEFAULT_MEMORY_MB,
            "default_cpu_limit": DEFAULT_CPU_LIMIT,
            "pids_limit": DEFAULT_PIDS_LIMIT,
            "network": "none",
        },
    }
    try:
        import docker
        from docker.errors import ImageNotFound
    except ImportError:
        report["docker"] = {"ok": False, "detail": "docker SDK not installed"}
        return report

    try:
        client = docker.from_env(timeout=10)
        client.ping()
        report["docker"] = {"ok": True, "detail": "daemon reachable"}
    except Exception as exc:  # noqa: BLE001
        report["docker"] = {"ok": False, "detail": f"daemon unreachable ({type(exc).__name__})"}
        return report

    for key, image in DEFAULT_IMAGES.items():
        try:
            client.images.get(image)
            report["images"][image] = {"ok": True}
        except ImageNotFound:
            report["images"][image] = {"ok": False, "detail": "missing"}
        except Exception as exc:  # noqa: BLE001
            report["images"][image] = {"ok": False, "detail": type(exc).__name__}

    if probe_exec and any(v.get("ok") for v in report["images"].values()):
        image = next(
            (img for img, meta in report["images"].items() if meta.get("ok")),
            None,
        )
        if image:
            container = None
            try:
                container = client.containers.run(
                    image=image,
                    command=["true"] if "python" in image else ["node", "-e", "process.exit(0)"],
                    network_disabled=True,
                    mem_limit="128m",
                    nano_cpus=int(0.5 * 1e9),
                    pids_limit=32,
                    cap_drop=["ALL"],
                    security_opt=["no-new-privileges"],
                    remove=False,
                    detach=True,
                )
                result = container.wait(timeout=15)
                report["probe_exec"] = {
                    "ok": int(result.get("StatusCode", 1)) == 0,
                    "detail": f"image={image}",
                }
            except Exception as exc:  # noqa: BLE001
                report["probe_exec"] = {"ok": False, "detail": type(exc).__name__}
            finally:
                if container is not None:
                    try:
                        container.remove(force=True, v=True)
                    except Exception:  # noqa: BLE001
                        pass
    return report


# Back-compat for existing imports
async def run_tests(
    workspace: Path,
    command: str,
    *,
    timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
) -> dict[str, Any]:
    return await get_challenge_runner().run_tests(
        workspace, command, timeout_seconds=timeout_seconds
    )


def _ensure_prebuilt_deps(workspace: Path, *, challenge_slug: str = "") -> None:
    """
    Copy a prebuilt Python virtualenv from the challenge source when one exists.
    Node dependencies are installed separately for the Linux runner.
    """
    if not challenge_slug:
        return
    try:
        from app.services.interview.registry import challenge_dir

        src_root = challenge_dir(challenge_slug)
    except (FileNotFoundError, ValueError, ImportError):
        return
    for name in (".venv",):
        target = workspace / name
        source = src_root / name
        if target.exists() or not source.exists():
            continue
        try:
            shutil.copytree(source, target, dirs_exist_ok=True, symlinks=True)
        except OSError:
            logger.warning("Could not copy prebuilt %s for %s", name, challenge_slug)


def _interview_network(client: Any) -> str:
    name = "promptcode-interview-internal"
    try:
        client.networks.get(name)
    except Exception:
        client.networks.create(name, internal=True, check_duplicate=True)
    return name


_NODE_MANIFESTS = ("package.json", "package-lock.json", "npm-shrinkwrap.json", ".npmrc")


def starter_snapshot_for_workspace(workspace: Path) -> Path:
    return Path(str(workspace) + ".starter")


def restore_node_manifests(workspace: Path) -> bool:
    """Put package manifests back from the immutable starter snapshot.

    Candidate code can rewrite these files during a test run. The next install
    must not execute that copy. Returns False when there is no trusted snapshot.
    """
    starter = starter_snapshot_for_workspace(workspace)
    if not starter.is_dir():
        return False
    for name in _NODE_MANIFESTS:
        src = starter / name
        dest = workspace / name
        if src.is_file():
            data = src.read_bytes()
            if dest.is_symlink() or not dest.is_file() or dest.read_bytes() != data:
                if dest.is_symlink() or dest.exists():
                    dest.unlink()
                dest.write_bytes(data)
        elif dest.is_symlink() or dest.exists():
            dest.unlink()
    return True


def node_install_argv(workspace: Path) -> list[str]:
    locked = (workspace / "package-lock.json").is_file() or (
        workspace / "npm-shrinkwrap.json"
    ).is_file()
    command = "ci" if locked else "install"
    return ["npm", command, "--ignore-scripts", "--no-audit", "--no-fund"]


def linux_npm_docker_argv(workspace: Path, image: str, install: list[str]) -> list[str]:
    """Offline install validation in disposable tmpfs; never mutate host dependencies."""
    script = ": > /tmp/promptcode-global.npmrc && cp -R /source/. /workspace/ && " + shlex.join(install + [
        "--offline", "--userconfig=/dev/null", "--globalconfig=/tmp/promptcode-global.npmrc",
    ])
    return [
        "docker", "run", "--rm", "--cap-drop", "ALL", "--security-opt", "no-new-privileges",
        "--pids-limit", "128", "--memory", "512m", "--cpus", "1", "--network", "none",
        "-v", f"{workspace}:/source:ro", "-w", "/workspace", "--user", "10001:10001",
        "--read-only", "--tmpfs", "/workspace:rw,nosuid,nodev,size=256m,uid=10001,gid=10001,mode=0700",
        "--tmpfs", "/tmp:rw,noexec,nosuid,size=64m", "-e", "HOME=/tmp",
        "-e", "npm_config_cache=/tmp/npm-cache", "-e", "npm_config_ignore_scripts=true",
        "-e", "npm_config_userconfig=/dev/null", "-e", "npm_config_globalconfig=/tmp/promptcode-global.npmrc",
        image, "sh", "-c", script,
    ]


def _install_linux_node_modules(workspace: Path, image: str) -> None:
    """Legacy validation helper; installs are discarded, never mounted back into API storage."""
    if not restore_node_manifests(workspace) or not (workspace / "package.json").is_file():
        return
    try:
        completed = subprocess.run(linux_npm_docker_argv(workspace, image, node_install_argv(workspace)),
                                   check=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
    except (OSError, subprocess.TimeoutExpired):
        logger.warning("Offline dependency validation unavailable")
        return
    if completed.returncode != 0:
        logger.warning("Offline dependencies unavailable in reviewed runner image/cache")


def _clip(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    return text[-limit:]


def _scrub_host_paths(text: str, workspace: Path) -> str:
    """Avoid leaking host Docker/workspace paths into candidate-visible output."""
    cleaned = text.replace(str(workspace), WORKSPACE_MOUNT)
    # Generic home / var tmp scrub
    cleaned = re.sub(r"/Users/[^/\s]+/", "/home/candidate/", cleaned)
    cleaned = re.sub(r"/home/[^/\s]+/", "/home/candidate/", cleaned)
    cleaned = re.sub(r"/var/folders/[^\s]+", "/tmp/", cleaned)
    return cleaned


def _result(
    *,
    ok: bool,
    exit_code: int,
    stdout: str,
    stderr: str,
    command: str,
    duration_ms: int,
    mode: str,
    counts: dict[str, int] | None = None,
    isolation: str = "host",
    timed_out: bool = False,
    command_id: str | None = None,
    runner: str | None = None,
    error_code: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "ok": ok,
        "advisory": True,
        "authoritative": False,
        "feedback_kind": "advisory_practice",
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "command": command,
        "duration_ms": duration_ms,
        "mode": mode,
        "counts": counts
        or {"passed": 0, "failed": 0, "skipped": 0, "total": 0},
        "isolation": isolation,
        "timed_out": timed_out,
        "command_id": command_id or "run_tests",
        "runner": runner or ("docker" if isolation == "docker" else "local"),
    }
    if error_code:
        payload["error_code"] = error_code
    return payload


def _parse_test_counts(output: str) -> dict[str, int]:
    """Best-effort structured counts from vitest/pytest output (not a scraper grade)."""
    # pytest summaries can put failures first. Read the final summary line so
    # assertion text or earlier output cannot supply a partial count.
    summaries = re.findall(
        r"^[= \t]*((?:\d+\s+(?:passed|failed|skipped|errors?|warnings?|xfailed|xpassed|deselected)(?:,\s*)?)+)"
        r"(?:\s+in\s+[\d.]+s)?[= \t]*$",
        output,
        re.I | re.M,
    )
    if summaries:
        counts = {status.lower(): int(count) for count, status in re.findall(
            r"(\d+)\s+(passed|failed|skipped)", summaries[-1], re.I
        )}
        passed, failed, skipped = (counts.get(status, 0) for status in ("passed", "failed", "skipped"))
        return {
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "total": passed + failed + skipped,
        }
    # vitest: "Tests  2 failed | 2 passed (4)"
    m = re.search(
        r"Tests\s+(\d+)\s+failed\s*\|\s*(\d+)\s+passed\s*\((\d+)\)",
        output,
        re.I,
    )
    if m:
        failed, passed, total = int(m.group(1)), int(m.group(2)), int(m.group(3))
        return {"passed": passed, "failed": failed, "skipped": 0, "total": total}
    m = re.search(r"Tests\s+(\d+)\s+passed", output, re.I)
    if m:
        passed = int(m.group(1))
        return {"passed": passed, "failed": 0, "skipped": 0, "total": passed}
    return {"passed": 0, "failed": 0, "skipped": 0, "total": 0}
