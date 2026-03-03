"""Docker sandbox runner.

Executes user-submitted code inside an isolated container with:
- the promptcode SDK pre-installed
- OPENAI_API_KEY injected
- telemetry directory mounted
- time and resource limits enforced
"""

from __future__ import annotations

import json
import logging
import tempfile
import uuid
from pathlib import Path
from typing import Any

import docker
from docker.errors import ContainerError, ImageNotFound

from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SandboxResult:
    def __init__(
        self,
        *,
        success: bool,
        output: str,
        exit_code: int,
        telemetry: list[dict[str, Any]],
        error: str | None = None,
    ):
        self.success = success
        self.output = output
        self.exit_code = exit_code
        self.telemetry = telemetry
        self.error = error


def run_in_sandbox(
    code: str,
    entrypoint: str,
    challenge_config: dict[str, Any],
    *,
    run_id: str | None = None,
    input_overrides: dict[str, Any] | None = None,
) -> SandboxResult:
    """Execute user code in a Docker container and collect telemetry."""

    run_id = run_id or uuid.uuid4().hex[:12]

    with tempfile.TemporaryDirectory(prefix=f"pc_{run_id}_") as tmpdir:
        workspace = Path(tmpdir)
        telemetry_dir = workspace / "telemetry"
        telemetry_dir.mkdir()
        code_dir = workspace / "code"
        code_dir.mkdir()

        (code_dir / entrypoint).write_text(code)

        input_data = {**challenge_config.get("inputs", {}), **(input_overrides or {})}
        (code_dir / "input.json").write_text(json.dumps(input_data))

        for fname, content in challenge_config.get("files", {}).items():
            (code_dir / fname).write_text(content)

        client = docker.from_env()

        try:
            container = client.containers.run(
                image=settings.sandbox_image,
                command=f"python /workspace/{entrypoint}",
                volumes={
                    str(code_dir): {"bind": "/workspace", "mode": "ro"},
                    str(telemetry_dir): {"bind": "/tmp/promptcode_telemetry", "mode": "rw"},
                },
                environment={
                    "OPENAI_API_KEY": settings.openai_api_key,
                    "PROMPTCODE_TELEMETRY_DIR": "/tmp/promptcode_telemetry",
                },
                mem_limit=settings.sandbox_memory_limit,
                nano_cpus=int(settings.sandbox_cpu_limit * 1e9),
                network_disabled=False,  # needs outbound for OpenAI
                detach=False,
                stdout=True,
                stderr=True,
                remove=True,
                timeout=settings.sandbox_timeout_seconds,
            )
            stdout = container.decode("utf-8") if isinstance(container, bytes) else str(container)

        except ContainerError as exc:
            logger.warning("Container exited with error: %s", exc)
            return SandboxResult(
                success=False,
                output="",
                exit_code=exc.exit_status,
                telemetry=[],
                error=str(exc),
            )
        except ImageNotFound:
            logger.error("Sandbox image '%s' not found", settings.sandbox_image)
            return SandboxResult(
                success=False,
                output="",
                exit_code=-1,
                telemetry=[],
                error=f"Sandbox image '{settings.sandbox_image}' not found. Build it first.",
            )
        except Exception as exc:
            logger.exception("Unexpected sandbox error")
            return SandboxResult(
                success=False,
                output="",
                exit_code=-1,
                telemetry=[],
                error=str(exc),
            )

        telemetry = _read_telemetry(telemetry_dir)

        return SandboxResult(
            success=True,
            output=stdout,
            exit_code=0,
            telemetry=telemetry,
        )


def _read_telemetry(telemetry_dir: Path) -> list[dict[str, Any]]:
    calls_file = telemetry_dir / "calls.jsonl"
    if not calls_file.exists():
        return []

    records: list[dict[str, Any]] = []
    for line in calls_file.read_text().strip().splitlines():
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            logger.warning("Skipping malformed telemetry line")
    return records
