"""Fail before accepting requests when deployment secrets or isolation are unsafe."""
from app.core.config import _INSECURE_JWT_SECRETS, _looks_like_placeholder


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
