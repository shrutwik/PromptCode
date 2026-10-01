"""Challenge test execution — allowlisted commands only; no raw shell from clients."""

from __future__ import annotations

import asyncio
import logging
import os
import re
import shlex
import shutil
import time
import uuid
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Any

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


def runner_mode() -> str:
    """Resolved runner mode: local | docker. Prefers PROMPTCODE_RUNNER."""
    raw = (
        os.getenv("PROMPTCODE_RUNNER")
        or os.getenv("INTERVIEW_RUNNER")
        or "local"
    ).strip().lower()
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
        try:
            proc = await asyncio.create_subprocess_exec(
                *argv,
                cwd=str(workspace),
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
                ok=proc.returncode == 0,
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

    return docker.from_env()


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
        sem = _get_runner_semaphore()
        from app.core.config import get_settings

        acquire_timeout = max(1, int(get_settings().max_runners_acquire_timeout_seconds))
        try:
            await asyncio.wait_for(sem.acquire(), timeout=acquire_timeout)
        except TimeoutError:
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
        try:
            return await asyncio.to_thread(
                self._run_docker_sync,
                workspace.resolve(),
                command,
                timeout,
                command_id,
                cfg,
            )
        finally:
            sem.release()

    def _run_docker_sync(
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

        _ensure_prebuilt_deps(
            workspace,
            challenge_slug=str(runner_config.get("challengeSlug") or ""),
        )

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

        run_kwargs: dict[str, Any] = {
            "image": image,
            "command": argv,
            "name": name,
            "working_dir": WORKSPACE_MOUNT,
            "volumes": {
                str(workspace): {"bind": WORKSPACE_MOUNT, "mode": "rw"},
            },
            "environment": {
                "HOME": "/tmp",
                "npm_config_cache": "/tmp/npm-cache",
                "PIP_DISABLE_PIP_VERSION_CHECK": "1",
                # Block package installs during candidate runs (defense in depth).
                "npm_config_offline": "true",
            },
            "mem_limit": f"{memory_mb}m",
            "nano_cpus": int(cpu * 1e9),
            "network_disabled": True,
            "detach": True,
            "stdout": True,
            "stderr": True,
            "remove": False,
            "cap_drop": ["ALL"],
            "security_opt": ["no-new-privileges"],
            "pids_limit": pids,
            "labels": {
                "promptcode.role": "interview-runner",
                "promptcode.component": "interview",
                "promptcode.command_id": command_id,
            },
            # Never mount docker.sock; never pass host secrets.
        }

        timed_out = False
        exit_code = -1
        stdout = ""
        stderr = ""
        try:
            container = client.containers.run(**run_kwargs)
            try:
                wait_result = container.wait(timeout=timeout_seconds)
                exit_code = int(wait_result.get("StatusCode", 1))
            except Exception:
                timed_out = True
                try:
                    container.kill()
                except Exception:  # noqa: BLE001
                    pass
                exit_code = -1
                stderr = f"Timed out after {timeout_seconds}s"

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
                    container.remove(force=True)
                except Exception:  # noqa: BLE001
                    try:
                        client.containers.get(name).remove(force=True)
                    except Exception:  # noqa: BLE001
                        logger.warning("Failed to remove interview container %s", name)

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
            isolation="docker",
            timed_out=timed_out,
            command_id=command_id,
            runner="docker",
        )


def get_challenge_runner() -> ChallengeRunner:
    mode = runner_mode()
    if mode == "docker":
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
        client = docker.from_env()
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
                        container.remove(force=True)
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
    Copy prebuilt deps from challenge source if present.

    Never runs npm/pip install. Candidate runs must use offline/prebuilt deps
    (image toolchain + optional host-preinstalled node_modules/.venv).
    """
    if not challenge_slug:
        return
    try:
        from app.services.interview.registry import challenge_dir

        src_root = challenge_dir(challenge_slug)
    except (FileNotFoundError, ValueError, ImportError):
        return
    for name in ("node_modules", ".venv"):
        target = workspace / name
        source = src_root / name
        if target.exists() or not source.exists():
            continue
        try:
            shutil.copytree(source, target, dirs_exist_ok=True)
        except OSError:
            logger.warning("Could not copy prebuilt %s for %s", name, challenge_slug)


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
    # pytest: "3 passed, 1 failed, 2 skipped"
    m = re.search(
        r"(\d+)\s+passed(?:,\s*(\d+)\s+failed)?(?:,\s*(\d+)\s+skipped)?",
        output,
        re.I,
    )
    if m:
        passed = int(m.group(1))
        failed = int(m.group(2) or 0)
        skipped = int(m.group(3) or 0)
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
