from __future__ import annotations

import ipaddress
from functools import lru_cache
from pathlib import Path

from pydantic import AliasChoices, Field, model_validator
from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"
_DEFAULT_DATABASE_URL = "postgresql+asyncpg://promptcode:promptcode@localhost:5432/promptcode"
_INSECURE_JWT_SECRETS = {
    "",
    "change-me-in-production-use-a-real-secret-key",
    "local-dev-secret-change-in-production",
}
_INSECURE_SANDBOX_EXECUTOR_TOKENS = {
    "",
    "local-sandbox-executor-token",
}
_DEFAULT_AUTH_TRUSTED_PROXY_CIDRS = [
    "127.0.0.1/32",
    "::1/128",
]
_PLACEHOLDER_NORMALIZED_VALUES = {
    "changeme",
    "secret",
    "replaceme",
    "replaceit",
    "replacethiswitharandomsecret",
    "replacethiswithalongrandomsecret",
    "skplaceholder",
    "skyourkeyhere",
}


def _normalize_placeholder_candidate(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def _looks_like_placeholder(value: str) -> bool:
    return _normalize_placeholder_candidate(value) in _PLACEHOLDER_NORMALIZED_VALUES


def _is_localhost_domain(value: str) -> bool:
    normalized = value.strip().lower()
    return normalized in {"localhost", "127.0.0.1", "::1"} or normalized.startswith(
        ("localhost:", "127.0.0.1:", "[::1]:")
    )


class Settings(BaseSettings):
    app_name: str = "PromptCode"
    debug: bool = False
    environment: str = "development"
    allow_unsafe_local_runner: bool = False
    interview_internal_token: str = ""
    smtp_host: str = ""
    smtp_port: int = Field(default=587, ge=1, le=65535)
    smtp_username: str = ""
    smtp_password: str = ""
    password_reset_from_email: str = ""

    database_url: str = _DEFAULT_DATABASE_URL
    database_echo: bool = False

    interview_workspace_root: str = ""  # optional override for session workspaces
    runner: str = "local"
    session_ttl_hours: int = 24
    max_runners: int = 4
    max_runners_acquire_timeout_seconds: int = 15
    interview_max_ai_requests_per_session: int = 40
    auth_cookie_enabled: bool = False  # prefer HttpOnly cookies in prod when true
    auth_cookie_secure: bool = True
    auth_cookie_samesite: str = "lax"
    frontend_url: str = ""
    app_version: str = "0.1.0-beta"
    git_sha: str = ""
    # Private beta gate: when true, signup requires invite code or allowlisted email.
    beta_invite_required: bool = False
    beta_email_allowlist: str = ""  # comma-separated emails
    beta_default_cohort: str = "beta"
    beta_starter_challenge: str = "invoice-status-transition"
    log_level: str = "INFO"
    # Set True when using Supabase or any hosted Postgres that requires SSL
    database_ssl_require: bool = False
    # Optional CA bundle path for verified TLS connections.
    database_ssl_ca_file: str = ""

    openai_api_key: str = Field(
        default="",
        validation_alias=AliasChoices("PROMPTCODE_OPENAI_API_KEY", "OPENAI_API_KEY"),
    )
    openai_base_url: str = ""
    openai_model: str = "gpt-4o"
    # Primary model used for prompt-quality judging (LLM-as-judge).
    # Can be a single model id or a comma-separated list (priority order).
    prompt_judge_model: str = "gpt-4o"
    # Optional backup model used if primary prompt judge model fails.
    prompt_judge_fallback_model: str = "gpt-4o"
    evaluation_weight_profile_path: str = ""
    evaluation_weight_profile_lock_path: str = ""
    evaluation_weight_profile_enforce_lock: bool = True

    sandbox_image: str = "promptcode-sandbox:latest"
    sandbox_timeout_seconds: int = 120
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: float = 1.0
    sandbox_executor_url: str = ""
    sandbox_executor_token: str = ""
    sandbox_executor_max_concurrent_runs: int = 6
    sandbox_executor_acquire_timeout_seconds: int = 10

    evaluation_normal_runs: int = 5
    evaluation_adversarial_runs: int = 2
    evaluation_max_parallel_specs: int = 2
    evaluation_job_timeout_seconds: int = 1800
    submission_inline_queue_processing: bool = True
    submission_max_outstanding_jobs_per_user: int = 3
    worker_id: str = ""
    worker_heartbeat_interval_seconds: int = 5
    worker_heartbeat_timeout_seconds: int = 30

    jwt_secret: str = ""
    domain: str = Field(default="", validation_alias=AliasChoices("DOMAIN", "PROMPTCODE_DOMAIN"))
    auth_trusted_proxy_cidrs: list[str] = list(_DEFAULT_AUTH_TRUSTED_PROXY_CIDRS)

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    # Sentry DSN — leave empty to disable error tracking
    sentry_dsn: str = ""

    # Prometheus /metrics — set a non-empty value to require Authorization: Bearer <token>
    metrics_token: str = ""

    model_config = {
        "env_prefix": "PROMPTCODE_",
        "env_file": str(_ENV_FILE),
        "populate_by_name": True,
    }

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        errors: list[str] = []
        secret = str(self.jwt_secret or "").strip()
        if not secret:
            errors.append("PROMPTCODE_JWT_SECRET must be set.")
        self.jwt_secret = secret
        if not self.debug and (
            secret in _INSECURE_JWT_SECRETS or _looks_like_placeholder(secret)
        ):
            errors.append(
                "PROMPTCODE_JWT_SECRET must be changed from a placeholder or development default when PROMPTCODE_DEBUG is false."
            )
        normalized_proxy_cidrs: list[str] = []
        for raw_cidr in self.auth_trusted_proxy_cidrs:
            cidr = str(raw_cidr or "").strip()
            if not cidr:
                continue
            try:
                ipaddress.ip_network(cidr, strict=False)
            except ValueError:
                errors.append(
                    "PROMPTCODE_AUTH_TRUSTED_PROXY_CIDRS must contain valid IP addresses or CIDR ranges."
                )
                break
            normalized_proxy_cidrs.append(cidr)
        self.auth_trusted_proxy_cidrs = normalized_proxy_cidrs
        self.database_url = str(self.database_url or "").strip()
        if not self.database_url:
            errors.append("PROMPTCODE_DATABASE_URL must be set.")
        if not self.debug and self.database_url == _DEFAULT_DATABASE_URL:
            errors.append(
                "PROMPTCODE_DATABASE_URL must be changed from the local development default when PROMPTCODE_DEBUG is false."
            )
        self.domain = str(self.domain or "").strip()
        self.openai_api_key = str(self.openai_api_key or "").strip()
        if not self.debug:
            if not self.domain:
                errors.append("DOMAIN must be set when PROMPTCODE_DEBUG is false.")
            elif _is_localhost_domain(self.domain):
                errors.append("DOMAIN must not point at localhost when PROMPTCODE_DEBUG is false.")
            if not self.openai_api_key:
                errors.append("PROMPTCODE_OPENAI_API_KEY must be set when PROMPTCODE_DEBUG is false.")
            elif self.openai_api_key.lower().startswith("sk-placeholder") or _looks_like_placeholder(
                self.openai_api_key
            ):
                errors.append(
                    "PROMPTCODE_OPENAI_API_KEY must be changed from a placeholder value when PROMPTCODE_DEBUG is false."
                )
        self.sandbox_executor_url = str(self.sandbox_executor_url or "").strip()
        self.sandbox_executor_token = str(self.sandbox_executor_token or "").strip()
        if self.sandbox_executor_url and not self.sandbox_executor_token:
            errors.append(
                "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN must be set when PROMPTCODE_SANDBOX_EXECUTOR_URL is configured."
            )
        if (
            not self.debug
            and self.sandbox_executor_url
            and (
                self.sandbox_executor_token in _INSECURE_SANDBOX_EXECUTOR_TOKENS
                or _looks_like_placeholder(self.sandbox_executor_token)
            )
        ):
            errors.append(
                "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN must be changed from a placeholder or development default when PROMPTCODE_DEBUG is false."
            )
        if self.sandbox_executor_max_concurrent_runs < 1:
            errors.append("PROMPTCODE_SANDBOX_EXECUTOR_MAX_CONCURRENT_RUNS must be at least 1.")
        if self.sandbox_executor_acquire_timeout_seconds < 1:
            errors.append("PROMPTCODE_SANDBOX_EXECUTOR_ACQUIRE_TIMEOUT_SECONDS must be at least 1.")
        if self.session_ttl_hours < 1:
            errors.append("PROMPTCODE_SESSION_TTL_HOURS must be at least 1.")
        if self.max_runners < 1:
            errors.append("PROMPTCODE_MAX_RUNNERS must be at least 1.")
        if self.max_runners_acquire_timeout_seconds < 1:
            errors.append("PROMPTCODE_MAX_RUNNERS_ACQUIRE_TIMEOUT_SECONDS must be at least 1.")
        if self.interview_max_ai_requests_per_session < 1:
            errors.append("PROMPTCODE_INTERVIEW_MAX_AI_REQUESTS_PER_SESSION must be at least 1.")
        samesite = str(self.auth_cookie_samesite or "lax").strip().lower()
        if samesite not in {"lax", "strict", "none"}:
            errors.append("PROMPTCODE_AUTH_COOKIE_SAMESITE must be lax, strict, or none.")
        self.auth_cookie_samesite = samesite
        if not self.debug and "*" in {o.strip() for o in self.cors_origins}:
            errors.append("PROMPTCODE_CORS_ORIGINS must not include * when PROMPTCODE_DEBUG is false.")
        # Cookie Secure defaults true; allow insecure cookies only in debug.
        if self.debug and not self.auth_cookie_secure:
            pass
        elif not self.debug:
            self.auth_cookie_secure = True
        self.frontend_url = str(self.frontend_url or "").strip()
        self.log_level = str(self.log_level or "INFO").strip().upper() or "INFO"
        if self.evaluation_max_parallel_specs < 1:
            errors.append("PROMPTCODE_EVALUATION_MAX_PARALLEL_SPECS must be at least 1.")
        if self.submission_max_outstanding_jobs_per_user < 1:
            errors.append("PROMPTCODE_SUBMISSION_MAX_OUTSTANDING_JOBS_PER_USER must be at least 1.")
        self.worker_id = str(self.worker_id or "").strip()
        if self.worker_heartbeat_interval_seconds < 1:
            errors.append("PROMPTCODE_WORKER_HEARTBEAT_INTERVAL_SECONDS must be at least 1.")
        if self.worker_heartbeat_timeout_seconds < self.worker_heartbeat_interval_seconds:
            errors.append(
                "PROMPTCODE_WORKER_HEARTBEAT_TIMEOUT_SECONDS must be greater than or equal to PROMPTCODE_WORKER_HEARTBEAT_INTERVAL_SECONDS."
            )
        if errors:
            raise ValueError("Invalid PromptCode environment:\n- " + "\n- ".join(dict.fromkeys(errors)))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
