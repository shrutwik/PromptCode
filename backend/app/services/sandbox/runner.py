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
import re
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any

import docker
import httpx
from docker.errors import APIError, ContainerError, ImageNotFound

from app.core.config import get_settings
from app.services.sandbox.relay import SandboxLLMBudget, SandboxLLMRelay

logger = logging.getLogger(__name__)
settings = get_settings()
_SANDBOX_PIDS_LIMIT = 128


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


def _is_safe_support_file_path(path_value: str) -> bool:
    normalized = str(path_value or "").strip().replace("\\", "/")
    if not normalized or normalized.startswith("/"):
        return False
    path = PurePosixPath(normalized)
    parts = path.parts
    if any(part in ("", ".", "..") for part in parts):
        return False
    return True


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

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "output": self.output,
            "exit_code": self.exit_code,
            "telemetry": self.telemetry,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "SandboxResult":
        return cls(
            success=bool(payload.get("success")),
            output=str(payload.get("output") or ""),
            exit_code=int(payload.get("exit_code", -1)),
            telemetry=list(payload.get("telemetry") or []),
            error=str(payload.get("error")) if payload.get("error") is not None else None,
        )


def run_in_sandbox(
    code: str,
    entrypoint: str,
    challenge_config: dict[str, Any],
    *,
    run_id: str | None = None,
    input_overrides: dict[str, Any] | None = None,
) -> SandboxResult:
    """Execute user code in a Docker container and collect telemetry."""
    if getattr(settings, "execution_broker_url", ""):
        from app.services.sandbox.legacy_broker_client import run_legacy_broker
        return run_legacy_broker(code, entrypoint, challenge_config, settings=settings,
                                 run_id=run_id, input_overrides=input_overrides)
    if _sandbox_executor_enabled():
        return _run_in_sandbox_remote(
            code,
            entrypoint,
            challenge_config,
            run_id=run_id,
            input_overrides=input_overrides,
        )
    return _run_in_sandbox_local(
        code,
        entrypoint,
        challenge_config,
        run_id=run_id,
        input_overrides=input_overrides,
    )


def _run_in_sandbox_local(
    code: str, entrypoint: str, challenge_config: dict[str, Any], *,
    run_id: str | None = None, input_overrides: dict[str, Any] | None = None,
    relay_factory=None,
) -> SandboxResult:
    from app.services.runner_capacity import RunnerBusy, execution_slot
    try:
        with execution_slot():
            return _run_in_sandbox_with_slot(code, entrypoint, challenge_config, run_id=run_id, input_overrides=input_overrides, relay_factory=relay_factory)
    except RunnerBusy:
        return SandboxResult(success=False, output='', exit_code=-1, telemetry=[], error='Execution capacity reached. Retry shortly.')


def _run_in_sandbox_with_slot(
    code: str,
    entrypoint: str,
    challenge_config: dict[str, Any],
    *,
    run_id: str | None = None,
    input_overrides: dict[str, Any] | None = None,
    relay_factory=None,
) -> SandboxResult:
    """Execute user code locally via the Docker daemon and collect telemetry."""

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
        # No telemetry directory is mounted into the candidate container. The
        # application relay records provider usage itself, so a candidate cannot
        # forge cost, token or prompt-quality accounting by writing files.
        telemetry_dir = workspace / "telemetry"
        code_dir = workspace / "code"
        code_dir.mkdir()

        (code_dir / entrypoint).write_text(code)

        input_data = {**challenge_config.get("inputs", {}), **(input_overrides or {})}
        (code_dir / "input.json").write_text(json.dumps(input_data))

        try:
            _write_support_files(code_dir, challenge_config.get("files", {}) or {})
        except ValueError as exc:
            logger.warning("Invalid sandbox support file: %s", exc)
            return SandboxResult(
                success=False,
                output="",
                exit_code=-1,
                telemetry=[],
                error="Invalid challenge file configuration.",
            )

        client = docker.from_env(timeout=10)
        container = None
        trusted_telemetry: list[dict[str, Any]] = []

        try:
            llm_budget = _build_sandbox_llm_budget(challenge_config)
            network_mode = _sandbox_network_mode()
            with (relay_factory or SandboxLLMRelay)(
                api_key=settings.openai_api_key,
                base_url=settings.openai_base_url,
                host_alias=_sandbox_host_alias(network_mode),
                budget=llm_budget,
                default_model=settings.openai_model,
                billing_identity=challenge_config.get("_ai_billing_identity"),
            ) as relay:
                run_kwargs = _build_container_run_kwargs(
                    code_dir=code_dir,
                    telemetry_dir=telemetry_dir,
                    entrypoint=entrypoint,
                    relay=relay,
                    budget=llm_budget,
                    network_mode=network_mode,
                    run_id=run_id,
                )
                container = client.containers.run(**run_kwargs)
                wait_result = container.wait(timeout=settings.sandbox_timeout_seconds)
                exit_code = int(wait_result.get("StatusCode", 1))
                logs = container.logs(stdout=True, stderr=True)
                stdout = logs.decode("utf-8", errors="replace") if isinstance(logs, (bytes, bytearray)) else str(logs)
                # Snapshot the relay's own accounting before the relay shuts down.
                recorder = getattr(relay, "recorded_calls", None)
                trusted_telemetry = recorder() if callable(recorder) else []
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
                error="Container exited with a non-zero status.",
            )
        except APIError as exc:
            logger.warning("Container API error: %s", exc)
            return SandboxResult(
                success=False,
                output="",
                exit_code=-1,
                telemetry=[],
                error="Sandbox container failed to start.",
            )
        except ImageNotFound:
            logger.error("Sandbox image '%s' not found", settings.sandbox_image)
            return SandboxResult(
                success=False,
                output="",
                exit_code=-1,
                telemetry=[],
                error="Sandbox image not found. Contact an administrator.",
            )
        except Exception:
            logger.exception("Unexpected sandbox error")
            return SandboxResult(
                success=False,
                output="",
                exit_code=-1,
                telemetry=[],
                error="An unexpected sandbox error occurred.",
            )
        finally:
            if container is not None:
                try:
                    container.remove(force=True)
                except Exception:
                    pass

        # Provider usage comes from the application relay that was actually billed.
        # Nothing the candidate container wrote is consulted.
        return SandboxResult(
            success=True,
            output=stdout,
            exit_code=0,
            telemetry=trusted_telemetry,
        )


def _run_in_sandbox_remote(
    code: str,
    entrypoint: str,
    challenge_config: dict[str, Any],
    *,
    run_id: str | None = None,
    input_overrides: dict[str, Any] | None = None,
) -> SandboxResult:
    run_id = run_id or uuid.uuid4().hex[:12]
    if not _is_safe_entrypoint(entrypoint):
        return SandboxResult(
            success=False,
            output="",
            exit_code=-1,
            telemetry=[],
            error="Unsafe entrypoint path",
        )

    payload = {
        "code": code,
        "entrypoint": entrypoint,
        "challenge_config": challenge_config,
        "run_id": run_id,
        "input_overrides": input_overrides or {},
    }
    headers = {"Authorization": f"Bearer {settings.sandbox_executor_token}"}
    timeout_seconds = max(30.0, float(settings.sandbox_timeout_seconds) + 15.0)
    endpoint = f"{str(settings.sandbox_executor_url).rstrip('/')}/v1/sandbox/run"

    try:
        with httpx.Client(timeout=timeout_seconds) as client:
            response = client.post(endpoint, json=payload, headers=headers)
    except httpx.HTTPError as exc:
        logger.warning("Sandbox executor request failed: %s", exc)
        return SandboxResult(
            success=False,
            output="",
            exit_code=-1,
            telemetry=[],
            error=f"Sandbox executor unavailable: {exc}",
        )

    if response.status_code != 200:
        detail = response.text[:500]
        logger.warning(
            "Sandbox executor returned %s: %s",
            response.status_code,
            detail,
        )
        return SandboxResult(
            success=False,
            output="",
            exit_code=-1,
            telemetry=[],
            error=f"Sandbox executor request failed ({response.status_code}): {detail}",
        )

    try:
        return SandboxResult.from_dict(response.json())
    except ValueError as exc:
        logger.warning("Sandbox executor returned invalid payload: %s", exc)
        return SandboxResult(
            success=False,
            output="",
            exit_code=-1,
            telemetry=[],
            error="Sandbox executor returned invalid JSON payload.",
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


def _write_support_files(code_dir: Path, files: dict[str, Any]) -> None:
    for fname, content in files.items():
        if not _is_safe_support_file_path(fname):
            raise ValueError(f"Unsafe challenge file path: {fname}")
        relative_path = PurePosixPath(str(fname).strip().replace("\\", "/"))
        dest = code_dir.joinpath(*relative_path.parts)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(str(content))


def _build_sandbox_llm_budget(challenge_config: dict[str, Any]) -> SandboxLLMBudget:
    constraints = challenge_config.get("constraints", {}) or {}
    raw_allowed_models = constraints.get("allowed_models")
    allowed_models = tuple(
        str(model).strip()
        for model in (raw_allowed_models or ("gpt-4o", "gpt-4o-mini"))
        if str(model).strip()
    ) or ("gpt-4o", "gpt-4o-mini")

    # Challenge-declared models are never replaced. A deployment may additionally
    # accept legacy provider model aliases from old candidates; the relay maps every
    # accepted alias to the configured model before any paid call. This is
    # deployment configuration, not a hardcoded vendor assumption.
    extra_aliases = tuple(
        alias.strip() for alias in str(getattr(settings, "ai_model_aliases", "") or "").split(",")
        if alias.strip()
    )
    if extra_aliases:
        allowed_models = tuple(dict.fromkeys((*allowed_models, *extra_aliases)))

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


def _sandbox_executor_enabled() -> bool:
    return bool(str(settings.sandbox_executor_url or "").strip())


def _build_container_run_kwargs(
    *,
    code_dir: Path,
    telemetry_dir: Path,
    entrypoint: str,
    relay: SandboxLLMRelay,
    budget: SandboxLLMBudget,
    network_mode: str | None,
    run_id: str,
) -> dict[str, Any]:
    # ``telemetry_dir`` is accepted for signature compatibility but is deliberately
    # NOT mounted: a candidate-writable telemetry file could forge cost, token and
    # prompt-quality accounting. Usage is taken from ``relay.recorded_calls()``.
    del telemetry_dir
    run_kwargs: dict[str, Any] = {
        "image": settings.sandbox_image,
        "command": ["python", f"/workspace/{entrypoint}"],
        "working_dir": "/workspace",
        "user": "runner",
        "volumes": {
            str(code_dir): {"bind": "/workspace", "mode": "ro"},
        },
        "environment": _build_container_environment(relay=relay, budget=budget),
        "mem_limit": settings.sandbox_memory_limit,
        "nano_cpus": int(settings.sandbox_cpu_limit * 1e9),
        "network_disabled": network_mode == "none",
        "detach": True,
        "stdout": True,
        "stderr": True,
        "remove": False,
        "cap_drop": ["ALL"],
        "security_opt": ["no-new-privileges"],
        "pids_limit": _SANDBOX_PIDS_LIMIT,
        "labels": {
            "promptcode.role": "sandbox",
            "promptcode.run_id": run_id,
        },
    }
    if getattr(settings, "execution_broker_mode", False):
        # Candidate telemetry is writable only in bounded ephemeral memory. The
        # application relay records authoritative provider usage independently.
        run_kwargs["volumes"] = {str(code_dir): {"bind": "/workspace", "mode": "ro"}}
        run_kwargs["read_only"] = True
        run_kwargs["tmpfs"] = {"/tmp": "rw,noexec,nosuid,nodev,size=64m"}
        run_kwargs["log_config"] = {"type": "local", "config": {"max-size": "1m", "max-file": "1", "compress": "false"}}
        run_kwargs["labels"].update({"promptcode.component": "execution-broker",
            "promptcode.expires_at": str(__import__("time").time() + settings.sandbox_timeout_seconds + 30)})
    extra_hosts = _build_extra_hosts(network_mode)
    if extra_hosts:
        run_kwargs["extra_hosts"] = extra_hosts
    if network_mode:
        run_kwargs["network_mode"] = network_mode
    return run_kwargs


def _sandbox_temp_root() -> Path | None:
    raw = str(os.environ.get("PROMPTCODE_SANDBOX_HOST_WORKDIR") or "").strip()
    if not raw:
        return None

    root = Path(raw)
    root.mkdir(parents=True, exist_ok=True)
    return root


def _build_extra_hosts(network_mode: str | None = None) -> dict[str, str] | None:
    if network_mode and network_mode.startswith("container:"):
        return None
    if sys.platform.startswith("linux"):
        return {"host.docker.internal": "host-gateway"}
    return None


def _sandbox_host_alias(network_mode: str | None = None) -> str:
    if network_mode and network_mode.startswith("container:"):
        return "127.0.0.1"
    return "host.docker.internal"


def _sandbox_network_mode() -> str | None:
    raw = str(os.environ.get("PROMPTCODE_SANDBOX_NETWORK_MODE") or "").strip().lower()
    if not raw:
        return None
    if raw == "container":
        container_id = _current_container_id()
        if container_id:
            return f"container:{container_id}"
        logger.warning("PROMPTCODE_SANDBOX_NETWORK_MODE=container but HOSTNAME is not a container id")
        return None
    if raw in {"bridge", "none"}:
        return raw
    if raw == "host":
        logger.warning("Ignoring insecure PROMPTCODE_SANDBOX_NETWORK_MODE=host")
        return None
    if raw.startswith("container:"):
        logger.warning("Ignoring direct container network attachment override: %s", raw)
        return None
    logger.warning("Ignoring unsupported PROMPTCODE_SANDBOX_NETWORK_MODE=%s", raw)
    return None


def _current_container_id() -> str | None:
    raw = str(os.environ.get("HOSTNAME") or "").strip()
    if re.fullmatch(r"[0-9a-f]{12,64}", raw):
        return raw
    return None
