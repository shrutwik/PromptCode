"""Docker sandbox runner.

Executes user-submitted code inside an isolated container with:
- the promptcode SDK pre-installed
- a short-lived local LLM relay token instead of the raw upstream API key
- telemetry directory mounted
- time and resource limits enforced
"""

from __future__ import annotations

import json
import logging
import os
import sys
import tempfile
import uuid
from pathlib import Path
from pathlib import PurePosixPath
from typing import Any

import docker
from docker.errors import APIError, ContainerError, ImageNotFound

from app.core.config import get_settings
from app.services.sandbox.relay import SandboxLLMBudget, SandboxLLMRelay

logger = logging.getLogger(__name__)
settings = get_settings()


def _is_safe_entrypoint(entrypoint: str) -> bool:
    normalized = str(entrypoint or "").strip().replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        return False
    path = PurePosixPath(normalized)
    if path.suffix != ".py":
        return False
    parts = path.parts
    if any(p in ("", ".", "..") for p in parts):
        return False
    return len(parts) == 1


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
    if not _is_safe_entrypoint(entrypoint):
        return SandboxResult(
            success=False,
            output="",
            exit_code=-1,
            telemetry=[],
            error="Unsafe entrypoint path",
        )

    temp_dir_kwargs: dict[str, str] = {}
    sandbox_root = _sandbox_temp_root()
    if sandbox_root is not None:
        temp_dir_kwargs["dir"] = str(sandbox_root)

    with tempfile.TemporaryDirectory(prefix=f"pc_{run_id}_", **temp_dir_kwargs) as tmpdir:
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
        container = None

        try:
            llm_budget = _build_sandbox_llm_budget(challenge_config)
            with SandboxLLMRelay(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                host_alias=_sandbox_host_alias(),
                budget=llm_budget,
            ) as relay:
                container = client.containers.run(
                    image=settings.sandbox_image,
                    command=["python", f"/workspace/{entrypoint}"],
                    volumes={
                        str(code_dir): {"bind": "/workspace", "mode": "ro"},
                        str(telemetry_dir): {"bind": "/tmp/promptcode_telemetry", "mode": "rw"},
                    },
                    environment=_build_container_environment(relay=relay, budget=llm_budget),
                    mem_limit=settings.sandbox_memory_limit,
                    nano_cpus=int(settings.sandbox_cpu_limit * 1e9),
                    network_disabled=False,
                    detach=True,
                    stdout=True,
                    stderr=True,
                    remove=False,
                    extra_hosts=_build_extra_hosts(),
                )
                wait_result = container.wait(timeout=settings.sandbox_timeout_seconds)
                exit_code = int(wait_result.get("StatusCode", 1))
                logs = container.logs(stdout=True, stderr=True)
                stdout = logs.decode("utf-8", errors="replace") if isinstance(logs, (bytes, bytearray)) else str(logs)
                if exit_code != 0:
                    raise ContainerError(
                        container=container,
                        exit_status=exit_code,
                        command=f"python /workspace/{entrypoint}",
                        image=settings.sandbox_image,
                        stderr=stdout.encode("utf-8", errors="ignore"),
                    )

        except ContainerError as exc:
            logger.warning("Container exited with error: %s", exc)
            return SandboxResult(
                success=False,
                output="",
                exit_code=exc.exit_status,
                telemetry=[],
                error=str(exc),
            )
        except APIError as exc:
            logger.warning("Container API error: %s", exc)
            return SandboxResult(
                success=False,
                output="",
                exit_code=-1,
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
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

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


def _build_sandbox_llm_budget(challenge_config: dict[str, Any]) -> SandboxLLMBudget:
    constraints = challenge_config.get("constraints", {}) or {}
    raw_allowed_models = constraints.get("allowed_models")
    allowed_models = tuple(
        str(model).strip()
        for model in (raw_allowed_models or ("gpt-4o", "gpt-4o-mini"))
        if str(model).strip()
    ) or ("gpt-4o", "gpt-4o-mini")

    max_llm_calls = int(constraints.get("max_llm_calls") or max(4, int(challenge_config.get("expected_calls", 3)) * 3))
    max_prompt_chars = int(challenge_config.get("max_prompt_chars") or 20_000)
    max_completion_tokens = int(challenge_config.get("max_completion_tokens") or 2_048)
    max_total_tokens = int(challenge_config.get("token_budget") or 12_000)
    max_total_cost_usd = float(challenge_config.get("cost_budget_usd") or 0.20)

    return SandboxLLMBudget(
        allowed_models=allowed_models,
        max_calls=max(1, max_llm_calls),
        max_prompt_chars=max(1_000, max_prompt_chars),
        max_completion_tokens=max(128, max_completion_tokens),
        max_total_tokens=max(1_000, max_total_tokens),
        max_total_cost_usd=max(0.01, max_total_cost_usd),
    )


def _build_container_environment(*, relay: SandboxLLMRelay, budget: SandboxLLMBudget) -> dict[str, str]:
    return {
        "PROMPTCODE_TELEMETRY_DIR": "/tmp/promptcode_telemetry",
        "PROMPTCODE_LLM_PROXY_URL": relay.proxy_url,
        "PROMPTCODE_LLM_PROXY_TOKEN": relay.token,
        "PROMPTCODE_ALLOWED_MODELS": ",".join(budget.allowed_models),
    }


def _sandbox_temp_root() -> Path | None:
    raw = str(os.environ.get("PROMPTCODE_SANDBOX_HOST_WORKDIR") or "").strip()
    if not raw:
        return None

    root = Path(raw)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _build_extra_hosts() -> dict[str, str] | None:
    if sys.platform.startswith("linux"):
        return {"host.docker.internal": "host-gateway"}
    return None


def _sandbox_host_alias() -> str:
    return "host.docker.internal"
