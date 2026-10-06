"""Execution backend selection.

``docker`` (the default) keeps today's self-managed container behaviour
byte-identical: the Docker branches call the same functions they always did, and
:class:`DockerExecutionBackend` simply delegates to them. ``modal`` routes the
same validated command bundles through :class:`ModalSandboxBackend`.
"""
from __future__ import annotations

import shlex
import threading
from pathlib import Path
from typing import Any, Sequence

from app.core.config import get_settings

from .modal_backend import ChallengeRunOutcome, ModalSandboxBackend

_modal_backend: ModalSandboxBackend | None = None
_modal_backend_lock = threading.Lock()


def get_execution_backend() -> "DockerExecutionBackend | ModalSandboxBackend":
    """Return the backend selected by ``PROMPTCODE_EXECUTION_BACKEND``.

    Defaults to docker. The modal package itself is imported lazily inside the
    backend's methods, so selecting docker never requires the Modal SDK.
    """
    name = str(get_settings().execution_backend or "docker").strip().lower()
    if name == "modal":
        global _modal_backend
        with _modal_backend_lock:
            if _modal_backend is None:
                _modal_backend = ModalSandboxBackend()
            return _modal_backend
    return DockerExecutionBackend()


class DockerExecutionBackend:
    """Adapter over the existing Docker execution code paths.

    This class deliberately contains no container policy of its own: it calls the
    same helper the synchronous Docker path already used, so switching backends
    cannot change Docker results or isolation.
    """

    name = "docker"

    def __init__(self, docker_client: Any = None) -> None:
        self._docker_client = docker_client

    def run_probe(
        self,
        *,
        source_dir: str | Path,
        argv: Sequence[str],
        image: str,
        timeout_seconds: int,
        output_limit_bytes: int,
    ) -> tuple[int, bytes]:
        from app.services.interview.trusted_evaluator import _run_probe_container

        return _run_probe_container(
            Path(source_dir),
            list(argv),
            image=image,
            timeout_seconds=timeout_seconds,
            docker_client=self._docker_client,
        )

    def run_challenge(
        self,
        *,
        source_dir: str | Path,
        argv: Sequence[str],
        image: str,
        timeout_seconds: int,
        memory_mb: int,
        cpu_limit: float,
        output_limit_bytes: int,
    ) -> ChallengeRunOutcome:
        """Run a bare allowlisted argv in Docker.

        ``argv`` must be the allowlisted command itself, not the Modal bootstrap
        wrapper: Docker supplies that layout through its runner image's run.sh.
        """
        from app.services.interview.runner import IsolatedRunner, resolve_command

        # Round-trip the allowlisted argv through the same resolver the live Docker
        # path uses; only an exact allowlisted template can survive this.
        command = resolve_command(shlex.join(argv))
        result: dict[str, Any] = IsolatedRunner()._run_docker_with_slot(
            Path(source_dir),
            command,
            timeout_seconds,
            "run_tests",
            {
                "image": image,
                "memoryMb": memory_mb,
                "cpuLimit": cpu_limit,
                "outputLimit": output_limit_bytes,
            },
        )
        return ChallengeRunOutcome(
            exit_code=int(result.get("exit_code", -1)),
            output=str(result.get("stdout") or "") + str(result.get("stderr") or ""),
            duration_ms=int(result.get("duration_ms") or 0),
            timed_out=bool(result.get("timed_out")),
        )
