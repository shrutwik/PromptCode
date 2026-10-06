"""Modal Sandbox execution backend.

Replaces the host-managed Docker container with a Modal Sandbox while keeping the
same command allowlisting, resource policy and observation contract. Security
properties enforced here, not by configuration:

- ``modal`` is imported lazily, so a Docker-only host needs no Modal SDK.
- Every sandbox is created with ``block_network=True``. Modal's default is that
  egress is ALLOWED, so this must be explicit and cannot be disabled.
- The environment is the fixed allowlist from :mod:`.policy`; nothing is copied
  from ``os.environ`` and secret-shaped keys are refused before creation.
- The sandbox is always terminated in a ``finally`` and an abort path
  (:meth:`ModalSandboxBackend.cancel`) terminates it from another thread.
- Captured output is truncated to the policy bound before it leaves the sandbox.

In-sandbox layout mirrors the Docker runner so the existing command builders work
unchanged: the validated source tree is uploaded to ``/source`` (the Docker
read-only bind mount) and the writable working copy is built at ``/workspace``.
For trusted probes the existing bootstrap in
``app/services/interview/trusted_evaluator.py`` performs that copy itself; for
advisory challenge runs :func:`bootstrap_argv` supplies the service-owned wrapper
that replaces ``/opt/promptcode-reporters/run.sh`` (which cannot be reused because
it sleeps to keep its tmpfs alive for a post-exit read).
"""
from __future__ import annotations

import contextlib
import inspect
import re
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence

from app.core.config import get_settings

from .policy import (
    DEPS_ROOT,
    SOURCE_MOUNT,
    WORKSPACE_MOUNT,
    SandboxPolicy,
    candidate_environment,
)

# A challenge slug is interpolated into a sandbox path, so only registered-looking
# slugs are accepted.
_SAFE_SLUG = re.compile(r"[a-z0-9][a-z0-9-]*")

# Dependency trees are supplied by the reviewed sandbox image, never by
# candidate-submitted files, so they are not uploaded.
_IGNORED_TREE_NAMES = frozenset({"node_modules", ".venv", "venv", "__pycache__", ".git"})

# Service-owned wrapper, the Modal equivalent of the Docker image's
# /opt/promptcode-reporters/run.sh minus its exit-marker tmpfs sleep. $1 is the
# validated challenge slug; the allowlisted argv is exec'd unchanged after it.
_BOOTSTRAP_SCRIPT = (
    "case \"$1\" in *[!a-z0-9-]*) exit 1 ;; esac\n"
    "cp -R /source/. /workspace/ || exit 1\n"
    "slug=$1\n"
    "shift\n"
    "if [ -n \"$slug\" ] && [ -d \"" + DEPS_ROOT + "/$slug/node_modules\" ]; then\n"
    "  mkdir -p /workspace/node_modules || exit 1\n"
    "  cp -as \"" + DEPS_ROOT + "/$slug/node_modules/.\" /workspace/node_modules/ || exit 1\n"
    "fi\n"
    "exec \"$@\"\n"
)


def bootstrap_argv(argv: Sequence[str], *, challenge_slug: str) -> list[str]:
    """Wrap an allowlisted argv with the service-owned Modal workspace bootstrap.

    Mirrors the Docker runner's ``run.sh`` layout (copy ``/source`` into the
    writable ``/workspace`` and link the reviewed per-challenge dependency layer
    when the image provides one) without the sleep-and-exit-marker step, because
    Modal reports the process exit code directly.
    """
    slug = str(challenge_slug or "").strip()
    if slug and _SAFE_SLUG.fullmatch(slug) is None:
        raise ValueError(f"Invalid challenge slug for sandbox bootstrap: {slug!r}")
    return ["sh", "-c", _BOOTSTRAP_SCRIPT, "promptcode-modal-bootstrap", slug, *argv]


class SandboxUnavailable(RuntimeError):
    """The Modal SDK or its required configuration is missing."""


class SandboxTimeout(RuntimeError):
    """A sandbox command exceeded its deadline.

    ``run_probe`` raises this instead of returning a value, because its
    ``tuple[int, bytes]`` result cannot carry a deadline signal. ``run_challenge``
    converts it into the Docker path's timed-out outcome (``exit_code=-1`` with
    ``timed_out=True``) rather than raising.
    """


class SandboxAborted(RuntimeError):
    """The run was cancelled through :meth:`ModalSandboxBackend.cancel`."""


@dataclass(frozen=True)
class ChallengeRunOutcome:
    """Result of one advisory candidate command run in a sandbox.

    ``timed_out`` mirrors the Docker path's flag so callers can distinguish a
    deadline from a candidate failure without guessing from the exit code.
    """

    exit_code: int
    output: str
    duration_ms: int
    timed_out: bool = False


def _import_modal() -> Any:
    """Import the optional Modal SDK, failing with an actionable message."""
    try:
        import modal  # noqa: PLC0415 - optional dependency, imported on demand
    except ImportError as exc:
        raise SandboxUnavailable(
            "PROMPTCODE_EXECUTION_BACKEND=modal requires the 'modal' package. "
            "Install modal on the execution host or keep the docker backend."
        ) from exc
    return modal


def modal_image_for(docker_image: str, argv: Sequence[str] = ()) -> str:
    """Map a Docker runner image reference onto the configured Modal image.

    Challenge ``runner.image`` values are Docker references such as
    ``promptcode-runner-python:latest``; Modal cannot pull those, so the stack is
    resolved to ``PROMPTCODE_MODAL_SANDBOX_IMAGE_NODE``/``_PYTHON`` instead. The
    allowlisted argv interpreter is checked first (probe argv starts with
    ``node``/``python``), then the Docker image name, mirroring how the Docker
    path picks ``DEFAULT_IMAGES``.
    """
    settings = get_settings()
    interpreter = Path(str(argv[0])).name if argv else ""
    if interpreter.startswith("python"):
        stack = "python"
    elif interpreter == "node":
        stack = "node"
    else:
        stack = "python" if "python" in str(docker_image or "").lower() else "node"
    image = (
        settings.modal_sandbox_image_python
        if stack == "python"
        else settings.modal_sandbox_image_node
    )
    if not image:
        raise SandboxUnavailable(f"No Modal sandbox image configured for the {stack} stack")
    return str(image)


def _accepts_keyword(function: Any, name: str) -> bool:
    """True when ``function`` can accept keyword ``name``.

    Modal's own ``Sandbox.create`` does not expose ``pids_limit`` on every SDK
    version, so the policy value is passed only when the installed version can
    enforce it rather than failing the whole run.
    """
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):
        return False
    if name in parameters:
        return True
    return any(
        parameter.kind is inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()
    )


def _is_timeout(error: BaseException) -> bool:
    if isinstance(error, TimeoutError):
        return True
    return "timeout" in type(error).__name__.lower()


def _terminate(sandbox: Any) -> None:
    """Terminate a sandbox, never raising: cleanup must not mask the real error."""
    if sandbox is None:
        return
    with contextlib.suppress(Exception):
        sandbox.terminate()


def _read_capped(stream: Any, limit: int) -> bytes:
    """Drain a Modal stream but retain only the last ``limit`` bytes.

    Draining is required so a chatty candidate cannot block on a full stream, and
    the tail is retained to match the Docker path's ``_clip`` behaviour.
    """
    buffer = bytearray()
    # Modal streams expose chunk iteration; read() takes no size and buffers
    # the entire output. Keep only the bounded tail while draining every chunk.
    for chunk in stream:
        buffer.extend(chunk[-limit:])
        if len(buffer) > limit:
            del buffer[: len(buffer) - limit]
    return bytes(buffer)


def _upload_source(sandbox: Any, source_dir: Path) -> None:
    """Copy a validated source tree to ``/source`` with Modal's filesystem API.

    The caller validates the directory (escape links, quota) before this runs; any
    symlink is skipped rather than recreated so a link can never redirect a write
    outside the sandbox. Dependency trees are skipped because the reviewed image
    supplies them, matching the Docker probe bootstrap's ignore list.
    """
    filesystem = sandbox.filesystem
    filesystem.make_directory(SOURCE_MOUNT)
    filesystem.make_directory(WORKSPACE_MOUNT)
    for path in sorted(source_dir.rglob("*")):
        relative = path.relative_to(source_dir)
        if any(part in _IGNORED_TREE_NAMES for part in relative.parts):
            continue
        remote = f"{SOURCE_MOUNT}/{relative.as_posix()}"
        if path.is_symlink():
            continue
        if path.is_dir():
            filesystem.make_directory(remote)
        elif path.is_file():
            filesystem.write_bytes(path.read_bytes(), remote)


def _create_kwargs(modal: Any, policy: SandboxPolicy, docker_image: str, argv: Sequence[str]):
    settings = get_settings()
    lookup_kwargs: dict[str, Any] = {"create_if_missing": True}
    if settings.modal_environment:
        lookup_kwargs["environment_name"] = settings.modal_environment
    app = modal.App.lookup(settings.modal_app_name, **lookup_kwargs)
    kwargs: dict[str, Any] = {
        "app": app,
        "image": modal.Image.from_registry(modal_image_for(docker_image, argv)),
        "env": dict(policy.environment),
        "timeout": policy.timeout_seconds,
        "workdir": WORKSPACE_MOUNT,
        "cpu": policy.cpu,
        "memory": policy.memory_mb,
        # Security-critical: Modal allows egress by default.
        "block_network": True,
    }
    if _accepts_keyword(modal.Sandbox.create, "pids_limit"):
        kwargs["pids_limit"] = policy.pids_limit
    return kwargs


class ModalSandboxBackend:
    """Runs candidate commands and trusted probes inside Modal Sandboxes."""

    name = "modal"

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._live: dict[str, Any] = {}
        self._aborted: set[str] = set()

    # -- abort path ---------------------------------------------------------

    def cancel(self, run_id: str | None = None) -> None:
        """Terminate live sandbox(es) so cancelled work cannot keep running.

        With no ``run_id`` every sandbox this backend created is terminated;
        ``run_id`` is internal and exists so a per-run abort does not kill an
        unrelated concurrent probe.

        NOTE: nothing calls this yet. A sandbox is still bounded in every case by its
        policy timeout, the Modal ``exec`` timeout and ``finally`` termination, so a
        dropped request cannot leave candidate code running indefinitely — but it does
        not stop early either. Wiring this to the request-disconnect path is a separate
        change, and its behaviour against real Modal is unverified.
        """
        with self._lock:
            ids = [run_id] if run_id is not None else list(self._live)
            targets = [(rid, self._live.pop(rid, None)) for rid in ids]
            self._aborted.update(rid for rid, _ in targets)
        for _, sandbox in targets:
            _terminate(sandbox)

    def _register(self, run_id: str, sandbox: Any) -> bool:
        """Track a sandbox unless it was already cancelled while starting."""
        with self._lock:
            if run_id in self._aborted:
                self._aborted.discard(run_id)
                return False
            self._live[run_id] = sandbox
            return True

    # -- public API ---------------------------------------------------------

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
        """Run one allowlisted candidate command; never raises for a timeout."""
        policy = SandboxPolicy(
            cpu=cpu_limit,
            memory_mb=memory_mb,
            timeout_seconds=self._bounded_timeout(timeout_seconds),
            pids_limit=get_settings().modal_sandbox_pids_limit,
            output_limit_bytes=output_limit_bytes,
            environment=candidate_environment(),
        )
        started = time.monotonic()
        try:
            exit_code, stdout, stderr = self._execute(
                source_dir=Path(source_dir), argv=list(argv), image=image, policy=policy
            )
        except SandboxTimeout:
            return ChallengeRunOutcome(
                exit_code=-1,
                output=f"Timed out after {policy.timeout_seconds}s",
                duration_ms=int((time.monotonic() - started) * 1000),
                timed_out=True,
            )
        # Modal (like docker logs here) multiplexes both streams; concatenate them
        # so the caller sees everything the command produced, then apply the policy
        # bound to the combined value as well as to each stream.
        combined = stdout + stderr
        output = combined[-policy.output_limit_bytes:].decode("utf-8", errors="replace")
        return ChallengeRunOutcome(
            exit_code=int(exit_code),
            output=output,
            duration_ms=int((time.monotonic() - started) * 1000),
        )

    def run_probe(
        self,
        *,
        source_dir: str | Path,
        argv: Sequence[str],
        image: str,
        timeout_seconds: int,
        output_limit_bytes: int,
    ) -> tuple[int, bytes]:
        """Run one trusted probe; returns ``(exit_code, stdout_bytes)``.

        Raises :class:`SandboxTimeout` on a deadline so the caller can map it onto
        the existing ``'timeout'`` observation error.
        """
        policy = SandboxPolicy(
            cpu=get_settings().modal_sandbox_cpu,
            memory_mb=get_settings().modal_sandbox_memory_mb,
            timeout_seconds=self._bounded_timeout(timeout_seconds),
            pids_limit=get_settings().modal_sandbox_pids_limit,
            output_limit_bytes=output_limit_bytes,
            environment=candidate_environment(),
        )
        exit_code, stdout, _ = self._execute(
            source_dir=Path(source_dir), argv=list(argv), image=image, policy=policy
        )
        return int(exit_code), stdout

    # -- internals ----------------------------------------------------------

    @staticmethod
    def _bounded_timeout(timeout_seconds: int) -> int:
        """Never let a sandbox outlive the configured maximum lifetime."""
        settings = get_settings()
        try:
            requested = int(timeout_seconds)
        except (TypeError, ValueError):
            requested = int(settings.modal_sandbox_timeout_seconds)
        return min(requested, int(settings.modal_sandbox_timeout_seconds))

    def _execute(
        self, *, source_dir: Path, argv: list[str], image: str, policy: SandboxPolicy
    ) -> tuple[int, bytes, bytes]:
        modal = _import_modal()
        run_id = uuid.uuid4().hex
        sandbox = None
        # Reserve the run id before the create RPC so a cancel() that arrives while
        # the sandbox is starting still terminates it.
        with self._lock:
            self._live[run_id] = None
        try:
            # Runner images exit by default. Keep the main process alive while
            # uploading source and executing commands; timeout/finally bound it.
            sandbox = modal.Sandbox.create(
                "sleep", "infinity", **_create_kwargs(modal, policy, image, argv)
            )
            if not self._register(run_id, sandbox):
                raise SandboxAborted("Sandbox run was cancelled")
            _upload_source(sandbox, source_dir)
            try:
                process = sandbox.exec(
                    *argv, timeout=policy.timeout_seconds, workdir=WORKSPACE_MOUNT,
                    text=False,
                )
                stdout = _read_capped(process.stdout, policy.output_limit_bytes)
                stderr = _read_capped(process.stderr, policy.output_limit_bytes)
                exit_code = process.wait()
            except Exception as exc:  # noqa: BLE001 - classify the deadline signal
                if _is_timeout(exc):
                    raise SandboxTimeout(
                        f"Sandbox command exceeded {policy.timeout_seconds}s"
                    ) from exc
                raise
            return (1 if exit_code is None else int(exit_code)), stdout, stderr
        finally:
            # The sandbox is terminated on success, failure, exception and
            # timeout; there is no path that leaves candidate code running.
            with self._lock:
                self._live.pop(run_id, None)
                self._aborted.discard(run_id)
            _terminate(sandbox)
