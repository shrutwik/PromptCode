"""Sandbox resource policy for candidate and trusted-grading execution.

Every value a caller supplies is clamped to a hard bound here, so a challenge
config or a broker payload can never widen a sandbox. Two properties are not
configurable at all:

- Network egress is always blocked. Modal Sandboxes allow egress by default, so
  forgetting ``block_network`` would silently expose the metadata/internal
  network. A caller that tries to disable it gets an error, not a weaker sandbox.
- The environment only ever contains entries from a fixed allowlist built here.
  Secret-bearing variable names are refused outright as defence in depth.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Mapping

WORKSPACE_MOUNT = "/workspace"
# The candidate tree is uploaded to /source, mirroring the Docker read-only bind
# mount, because both the trusted probe bootstrap and the advisory wrapper build
# /workspace from it.
SOURCE_MOUNT = "/source"
# Reviewed per-challenge Node dependencies are baked into the sandbox image at
# this path (see .images); the probe bootstrap links it into /workspace.
DEPS_ROOT = "/opt/promptcode-deps"

# Hard bounds. Callers may request less, never more.
MIN_CPU = 0.25
MAX_CPU = 16.0
MIN_MEMORY_MB = 128
MAX_MEMORY_MB = 65536
MIN_TIMEOUT_SECONDS = 1
MAX_TIMEOUT_SECONDS = 3600
MIN_PIDS_LIMIT = 16
MAX_PIDS_LIMIT = 4096
MIN_OUTPUT_LIMIT_BYTES = 1024
MAX_OUTPUT_LIMIT_BYTES = 4 * 1024 * 1024

# The only environment a sandbox that runs candidate code may see. Nothing is
# copied from os.environ: the parent process holds credentials.
SAFE_CANDIDATE_ENVIRONMENT: dict[str, str] = {
    "HOME": "/tmp",
    "TMPDIR": "/tmp",
    "PYTHONDONTWRITEBYTECODE": "1",
    "PIP_DISABLE_PIP_VERSION_CHECK": "1",
    "npm_config_cache": "/tmp/npm-cache",
    "npm_config_offline": "true",
    "npm_config_ignore_scripts": "true",
    "PYTHONPATH": WORKSPACE_MOUNT,
    "NODE_PATH": WORKSPACE_MOUNT,
    "PYTEST_ADDOPTS": (
        f"--rootdir {WORKSPACE_MOUNT} --confcutdir {WORKSPACE_MOUNT} --import-mode=prepend"
    ),
}

# Secret-shaped variable names. Exact names plus prefix/suffix families cover the
# credential set this service handles (``PROMPTCODE_*_TOKEN``, ``MODAL_TOKEN_*``,
# ``PROMPTCODE_SUPABASE_*``, ``*_KEY``, ``*_SECRET``).
FORBIDDEN_ENV_KEYS = frozenset(
    {
        "DEEPSEEK_API_KEY",
        "OPENAI_API_KEY",
        "PROMPTCODE_JWT_SECRET",
        "PROMPTCODE_DATABASE_URL",
        "GRADING_SIGNING_KEY",
    }
)
FORBIDDEN_ENV_PREFIXES = ("PROMPTCODE_SUPABASE_", "MODAL_TOKEN_")
FORBIDDEN_ENV_SUFFIXES = ("_TOKEN", "_SECRET", "_KEY", "_PASSWORD")


def candidate_environment() -> dict[str, str]:
    """Return a fresh copy of the fixed sandbox environment allowlist.

    Used for candidate runs and for trusted probes: both execute candidate code,
    so neither may ever receive a credential.
    """
    return dict(SAFE_CANDIDATE_ENVIRONMENT)


def is_secret_env_key(name: object) -> bool:
    """True when a variable name belongs to a credential family."""
    upper = str(name or "").strip().upper()
    if not upper:
        return False
    if upper in FORBIDDEN_ENV_KEYS:
        return True
    if upper.startswith(FORBIDDEN_ENV_PREFIXES):
        return True
    return upper.endswith(FORBIDDEN_ENV_SUFFIXES)


def assert_no_secret_env(environment: Mapping[str, object]) -> None:
    """Fail closed if a secret-bearing variable would enter a sandbox.

    Reports key names only, never values, so an error cannot leak a credential
    into logs.
    """
    offenders = sorted(str(name) for name in environment if is_secret_env_key(name))
    if offenders:
        raise ValueError(
            "Refusing to pass secret-bearing variables into a sandbox: " + ", ".join(offenders)
        )


def _clamp_int(value: object, low: int, high: int) -> int:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return low
    return max(low, min(number, high))


def _clamp_float(value: object, low: float, high: float) -> float:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return low
    if number != number:  # NaN
        return low
    return max(low, min(number, high))


@dataclass(frozen=True)
class SandboxPolicy:
    """Immutable, already-clamped resource policy for one sandbox."""

    cpu: float
    memory_mb: int
    timeout_seconds: int
    pids_limit: int
    output_limit_bytes: int
    environment: Mapping[str, str] = field(default_factory=candidate_environment)
    # Modal's default is that egress is ALLOWED, so this must be passed on every
    # create call. It is always True and cannot be turned off.
    block_network: bool = True

    def __post_init__(self) -> None:
        if self.block_network is not True:
            raise ValueError("Sandbox network egress can never be enabled")
        object.__setattr__(self, "block_network", True)
        object.__setattr__(self, "cpu", _clamp_float(self.cpu, MIN_CPU, MAX_CPU))
        object.__setattr__(
            self, "memory_mb", _clamp_int(self.memory_mb, MIN_MEMORY_MB, MAX_MEMORY_MB)
        )
        object.__setattr__(
            self,
            "timeout_seconds",
            _clamp_int(self.timeout_seconds, MIN_TIMEOUT_SECONDS, MAX_TIMEOUT_SECONDS),
        )
        object.__setattr__(
            self, "pids_limit", _clamp_int(self.pids_limit, MIN_PIDS_LIMIT, MAX_PIDS_LIMIT)
        )
        object.__setattr__(
            self,
            "output_limit_bytes",
            _clamp_int(
                self.output_limit_bytes, MIN_OUTPUT_LIMIT_BYTES, MAX_OUTPUT_LIMIT_BYTES
            ),
        )
        environment = {str(k): str(v) for k, v in dict(self.environment or {}).items()}
        assert_no_secret_env(environment)
        object.__setattr__(self, "environment", MappingProxyType(environment))
