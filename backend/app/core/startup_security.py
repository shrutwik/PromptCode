"""Fail before accepting requests when deployment secrets or isolation are unsafe."""
import os
from pathlib import Path
from typing import Any
from urllib.parse import ParseResult, urlparse

from app.core.config import _INSECURE_JWT_SECRETS, Settings, _looks_like_placeholder


def invalid_deployment_token(value: str) -> bool:
    value = str(value or "").strip().lower()
    return (
        not value
        or _looks_like_placeholder(value)
        or value.startswith(("change-me", "example", "replace-", "your-", "sk-placeholder"))
        or value in {"local-dev-secret-change-in-production", "local-sandbox-executor-token"}
    )


# Private link-local/RFC1918 names a same-host broker may legitimately use.
_PRIVATE_BROKER_HOSTS = {
    "broker", "sandbox-executor", "host.docker.internal",
    "127.0.0.1", "localhost", "::1",
}


def _same_host_broker_allowed(settings: Settings, broker: ParseResult) -> bool:
    """Whether a broker on this Docker host is explicitly permitted.

    The invariant this guard protects is that the *application* process never has
    Docker daemon access, which is checked separately. Requiring a different
    machine as well is hardening (smaller blast radius if the broker is
    compromised), not a functional requirement. A deployment may opt in to a
    same-host broker it placed on a private container network, where the broker
    URL cannot be reached from the internet and no TLS terminator is needed.
    """
    if not getattr(settings, "allow_same_host_broker", False):
        return False
    host = (broker.hostname or "").lower()
    if host not in _PRIVATE_BROKER_HOSTS:
        return False
    # Only a private/internal address may skip TLS; never a public hostname.
    return broker.scheme in {"http", "https"}


def _validate_docker_backend(settings: Any, errors: list[str]) -> None:
    """Self-managed execution host: today's checks, unchanged for this mode."""
    if settings.allow_unsafe_local_runner or settings.runner.strip().lower() != "docker":
        errors.append("Production requires PROMPTCODE_RUNNER=docker and the host runner disabled")
    broker = urlparse(str(getattr(settings, "execution_broker_url", "") or ""))
    if (broker.scheme != "https" or not broker.hostname
            or broker.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
            or broker.username or broker.password or broker.query or broker.fragment):
        errors.append("Production requires a separate HTTPS execution broker")
    if invalid_deployment_token(getattr(settings, "sandbox_executor_token", "")):
        errors.append("Execution broker management token must be configured")
    if len(str(getattr(settings, "sandbox_executor_token", "")).strip().encode()) < 32:
        errors.append("Execution broker management token must contain at least 32 bytes")


def _validate_modal_backend(settings: Any, errors: list[str]) -> None:
    """Modal + Supabase managed deployment: only what this mode actually needs.

    The Docker checks above must NOT run here. A Modal container has no Docker
    daemon, so requiring ``PROMPTCODE_RUNNER=docker``, an HTTPS execution broker,
    or a broker management token would reject a correct deployment. Conversely a
    ``/var/run/docker.sock`` that merely exists in a build image is harmless: this
    mode never *manages* containers through a Docker daemon, so only the broker
    role itself is an error.
    """
    if getattr(settings, "allow_unsafe_local_runner", False):
        errors.append("PROMPTCODE_EXECUTION_BACKEND=modal must not allow the unsafe local runner")
    if not (str(getattr(settings, "modal_sandbox_image_node", "") or "").strip()
            and str(getattr(settings, "modal_sandbox_image_python", "") or "").strip()):
        errors.append(
            "PROMPTCODE_MODAL_SANDBOX_IMAGE_NODE and PROMPTCODE_MODAL_SANDBOX_IMAGE_PYTHON "
            "must both be set when PROMPTCODE_EXECUTION_BACKEND=modal"
        )
    # Configured Docker reliance, not the existence of a socket on disk. Only the
    # broker *role* — this process managing containers through a Docker daemon — is
    # rejected. Broker and executor URLs are deliberately allowed: the
    # trusted-evaluation path may legitimately be wired through them, and forbidding
    # them here would block that wiring. A socket or DOCKER_HOST merely present in
    # the image is not a failure.
    if getattr(settings, "execution_broker_mode", False):
        errors.append("PROMPTCODE_EXECUTION_BACKEND=modal must not run the Docker execution broker role")
    # Modal web endpoints cap an HTTP request at 150 s and their 303 result-URL
    # fallback cannot populate CORS headers, so no request may *synchronously* wait
    # for grading. The durable grading queue plus its polling worker (see
    # backend/modal_app.py) keeps that invariant; submission evaluation additionally
    # runs as a post-response background task, never inside the response itself.
    storage_backend = str(getattr(settings, "storage_backend", "") or "").strip().lower()
    if storage_backend != "supabase":
        errors.append(
            "PROMPTCODE_STORAGE_BACKEND must be 'supabase' when "
            "PROMPTCODE_EXECUTION_BACKEND=modal (Modal containers have no persistent disk)"
        )
        return
    supabase = urlparse(str(getattr(settings, "supabase_url", "") or ""))
    if supabase.scheme != "https" or not supabase.hostname:
        errors.append(
            "PROMPTCODE_SUPABASE_URL must be an https project URL when "
            "PROMPTCODE_EXECUTION_BACKEND=modal"
        )
    if invalid_deployment_token(getattr(settings, "supabase_service_role_key", "")):
        errors.append(
            "PROMPTCODE_SUPABASE_SERVICE_ROLE_KEY must contain a non-example secret when "
            "PROMPTCODE_EXECUTION_BACKEND=modal"
        )


def validate_production_startup(settings: Any) -> None:
    if settings.debug and settings.environment.strip().lower() != "production":
        return
    errors = []
    if settings.debug:
        errors.append("PROMPTCODE_DEBUG must be false in production")
    # Validate the requirements of the *configured* execution backend. An unknown
    # value falls back to the Docker checks, which are the stricter set.
    execution_backend = str(getattr(settings, "execution_backend", "") or "").strip().lower()
    if execution_backend == "modal":
        _validate_modal_backend(settings, errors)
    else:
        _validate_docker_backend(settings, errors)
    # Deployment-independent invariant: the application process must never hold
    # Docker daemon access. This holds for the Modal backend too — a correct Modal
    # container has no socket and no DOCKER_HOST, so it passes trivially, while a
    # Modal-configured app mistakenly placed on a Docker host is still rejected.
    if Path("/var/run/docker.sock").exists() or os.environ.get("DOCKER_HOST", "").strip():
        errors.append("Application processes must not have Docker daemon access")
    if len(str(getattr(settings, "grading_signing_key", "")).strip().encode()) < 32:
        errors.append("Production grading signing key must contain at least 32 bytes")
    if invalid_deployment_token(getattr(settings, "grading_signing_key", "")):
        errors.append("Production grading signing key must not be an example or placeholder")
    for name, value in (
        ("PROMPTCODE_INTERVIEW_INTERNAL_TOKEN", settings.interview_internal_token),
        ("PROMPTCODE_METRICS_TOKEN", settings.metrics_token),
    ):
        if invalid_deployment_token(value):
            errors.append(f"{name} must contain a non-example secret")
    if settings.jwt_secret in _INSECURE_JWT_SECRETS or invalid_deployment_token(settings.jwt_secret):
        errors.append("PROMPTCODE_JWT_SECRET must not be a default or example")
    if errors:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(errors))
