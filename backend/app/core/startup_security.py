"""Fail before accepting requests when deployment secrets or isolation are unsafe."""
from app.core.config import _INSECURE_JWT_SECRETS, _looks_like_placeholder
import os
from pathlib import Path
from urllib.parse import urlparse


def invalid_deployment_token(value: str) -> bool:
    value = str(value or "").strip().lower()
    return (
        not value
        or _looks_like_placeholder(value)
        or value.startswith(("change-me", "example", "replace-", "your-", "sk-placeholder"))
        or value in {"local-dev-secret-change-in-production", "local-sandbox-executor-token"}
    )


def validate_production_startup(settings) -> None:
    if settings.debug and settings.environment.strip().lower() != "production":
        return
    errors = []
    if settings.debug:
        errors.append("PROMPTCODE_DEBUG must be false in production")
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
    if len(str(getattr(settings, "grading_signing_key", "")).strip().encode()) < 32:
        errors.append("Production grading signing key must contain at least 32 bytes")
    if Path("/var/run/docker.sock").exists() or os.environ.get("DOCKER_HOST", "").strip():
        errors.append("Application processes must not have Docker daemon access")
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
