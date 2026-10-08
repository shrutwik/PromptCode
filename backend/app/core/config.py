from __future__ import annotations

import ipaddress
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import NamedTuple
from urllib.parse import urlparse

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


# Built-in provider endpoints. A key configured for one provider is only ever
# paired with that provider's base URL, so a legacy key can never leak to a
# different vendor's endpoint.
_KNOWN_PROVIDER_BASE_URLS = {
    "deepseek": "https://api.deepseek.com",
    "openai": "https://api.openai.com/v1",
}
# Key field that belongs to each built-in provider.
_PROVIDER_KEY_ATTRS = {
    "deepseek": "deepseek_api_key",
    "openai": "openai_api_key",
}


class AICredentials(NamedTuple):
    """Effective AI provider credentials and the env var that supplied the key."""

    provider: str
    api_key: str
    base_url: str
    model: str
    key_env: str


def _provider_host_matches(provider: str, base_url: str) -> bool:
    """Whether ``base_url`` belongs to the built-in ``provider``."""
    host = (urlparse(base_url).hostname or "").lower()
    if not host:
        return False
    if provider == "deepseek":
        return host == "api.deepseek.com"
    if provider == "openai":
        return host == "api.openai.com" or host.endswith(".openai.com")
    return False


def resolve_ai_credentials(settings: "Settings") -> "AICredentials":
    """Resolve the effective AI ``(provider, api_key, base_url, model, key_env)``.

    No vendor is required: ``ai_provider`` selects the provider and an empty value is
    inferred from the configured base URL. Credentials resolve per provider so the
    effective key always belongs to the endpoint it is sent to, and a key issued for
    one built-in vendor is never paired with another vendor's endpoint.

    ``PROMPTCODE_OPENAI_API_KEY`` remains the generic provider key (its historical
    role in this codebase) and is used as the fallback for custom/named providers.
    The built-in providers use their own dedicated key so a credential can never be
    forwarded to a different vendor.
    """
    explicit_base = str(getattr(settings, "ai_base_url", "") or "").strip()
    inherited_base = str(getattr(settings, "openai_base_url", "") or "").strip()
    provider = str(getattr(settings, "ai_provider", "") or "").strip().lower()
    if not provider:
        probe = explicit_base or inherited_base
        host = (urlparse(probe).hostname or "").lower()
        if host == "api.deepseek.com":
            provider = "deepseek"
        elif host == "api.openai.com" or host.endswith(".openai.com"):
            provider = "openai"
        else:
            provider = "custom"
    model = str(getattr(settings, "ai_model", "") or "").strip()
    generic_key = str(getattr(settings, "openai_api_key", "") or "").strip()
    dedicated_key = str(getattr(settings, "ai_api_key", "") or "").strip()
    if dedicated_key:
        # An explicitly supplied generic AI key is authoritative: it is the
        # deployment's own credential for this feature and outranks any
        # provider-specific default.
        base_url = explicit_base or inherited_base
        return AICredentials(provider, dedicated_key, base_url, model, "PROMPTCODE_AI_API_KEY")
    if provider in _PROVIDER_KEY_ATTRS:
        api_key = str(getattr(settings, _PROVIDER_KEY_ATTRS[provider], "") or "").strip()
        key_env = "DEEPSEEK_API_KEY" if provider == "deepseek" else "PROMPTCODE_OPENAI_API_KEY"
        # Only a base URL that actually belongs to this provider may be paired with
        # this provider's key. An explicit base URL pointing at a different vendor is
        # a misconfiguration: fall back to the canonical endpoint here and let startup
        # validation report it instead of forwarding the credential.
        if explicit_base and _provider_host_matches(provider, explicit_base):
            base_url = explicit_base
        elif not explicit_base and _provider_host_matches(provider, inherited_base):
            base_url = inherited_base
        else:
            base_url = _KNOWN_PROVIDER_BASE_URLS[provider]
    else:
        # A named/custom provider falls back to the generic provider key field so
        # existing deployments keep working unchanged.
        api_key = generic_key
        key_env = "PROMPTCODE_OPENAI_API_KEY"
        base_url = explicit_base or inherited_base
    return AICredentials(provider, api_key, base_url, model, key_env)


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
    grading_signing_key: str = ""
    grading_feedback_enabled: bool = False
    grading_auto_enabled: bool = False
    grading_auto_model: str = "deepseek-flash"
    grading_publish_reviewed_scores: bool = False
    grading_calibration_report_path: str = ""
    grading_job_timeout_seconds: int = Field(default=600, ge=30, le=3600)
    grading_max_pending_jobs: int = Field(default=100, ge=1, le=10000)
    interview_storage_max_bytes: int = Field(default=20 * 1024**3, ge=1)
    interview_storage_min_free_bytes: int = Field(default=2 * 1024**3, ge=0)
    grading_queue_alert_seconds: int = Field(default=300, ge=1)
    grading_failed_alert_jobs: int = Field(default=1, ge=1)
    # local | docker. Empty process env falls through to this so a laptop .env is honored.
    runner: str = "local"
    # Candidate/trusted execution backend. ``docker`` preserves the existing
    # self-managed host path; ``modal`` runs the same validated command bundles in
    # Modal Sandboxes. See app/services/execution/backend.py.
    execution_backend: str = "docker"
    # Modal Sandboxes. ``MODAL_TOKEN_ID``/``MODAL_TOKEN_SECRET`` are read from the
    # environment by the Modal SDK and are never placed in a candidate sandbox.
    modal_app_name: str = "promptcode"
    modal_environment: str = ""
    modal_sandbox_image_node: str = ""
    modal_sandbox_image_python: str = ""
    modal_sandbox_timeout_seconds: int = Field(default=120, ge=5, le=3600)
    modal_sandbox_cpu: float = Field(default=1.0, gt=0, le=16.0)
    modal_sandbox_memory_mb: int = Field(default=1024, ge=128, le=65536)
    # Candidate output is truncated to this bound before it leaves the sandbox.
    modal_sandbox_output_limit_bytes: int = Field(default=131072, ge=1024, le=4 * 1024 * 1024)
    modal_sandbox_pids_limit: int = Field(default=128, ge=16, le=4096)
    modal_function_timeout_seconds: int = Field(default=1500, ge=60, le=86400)
    # Persistence backend. ``filesystem`` preserves local development; ``supabase``
    # keeps the database as the source of truth and objects in a private bucket.
    storage_backend: str = "filesystem"
    supabase_url: str = ""
    supabase_service_role_key: str = ""
    supabase_storage_bucket: str = "promptcode-private"
    supabase_storage_timeout_seconds: float = Field(default=30.0, gt=0, le=300)
    # Free-plan object cap is 50 MB; the application source quota is far below it,
    # so an upload that exceeds this is a configuration error, not a size error.
    supabase_max_object_bytes: int = Field(default=48 * 1024 * 1024, ge=1024)
    # Keeps a free Supabase project from being paused after 7 days of DB inactivity.
    supabase_keepalive_enabled: bool = True
    supabase_keepalive_interval_seconds: int = Field(default=6 * 3600, ge=60)
    session_ttl_hours: int = 24
    max_runners: int = 4
    max_runners_acquire_timeout_seconds: int = 15
    # Bounded waiting for execution slots. Requests queue FIFO up to
    # ``max_runner_waiters``; beyond that admission fails closed with a retry
    # hint instead of queueing without bound.
    max_runner_waiters: int = Field(default=32, ge=0, le=10000)
    # Independent grading probes executed inside one admitted execution slot.
    # Raising this shortens slot occupancy (a 3-7 case sweep at up to 12 s/case)
    # but increases concurrent probe containers on the execution host, so raise it
    # only with measured host evidence.
    probe_concurrency: int = Field(default=2, ge=1, le=8)
    # Database budgets. The statement cap must exceed the pool wait so a
    # transaction queued behind the pool is bounded by pool_timeout rather than
    # being killed mid-statement.
    database_pool_size: int = Field(default=20, ge=1, le=200)
    database_max_overflow: int = Field(default=10, ge=0, le=200)
    database_pool_timeout_seconds: float = Field(default=15.0, gt=0, le=300)
    database_command_timeout_seconds: float = Field(default=30.0, gt=0, le=600)
    database_connect_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    interview_max_ai_requests_per_session: int = 10
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
        # The field name is included so callers constructing Settings directly
        # (tests, the broker bootstrap) are honoured; a validation_alias alone
        # silently discards them and reports the key as missing.
        validation_alias=AliasChoices("PROMPTCODE_OPENAI_API_KEY", "OPENAI_API_KEY", "openai_api_key"),
    )
    deepseek_api_key: str = Field(default="", validation_alias=AliasChoices(
        "DEEPSEEK_API_KEY", "PROMPTCODE_DEEPSEEK_API_KEY", "deepseek_api_key"))
    openai_base_url: str = ""
    openai_model: str = "gpt-4o"
    # Interview assistant (answers questions in a session). Separate from the
    # evaluation model above so practice chat can stay on a cheaper model.
    ai_kill_switch: bool = False
    ai_max_micros_per_token: int = Field(default=2, ge=1)
    # An overall trial/lifetime cap is opt-in and has no default monetary ceiling.
    # Removing the old hardcoded $5 does NOT relax spending: the global, per-user
    # and per-session request/token/cost caps below stay enforced, and the kill
    # switch still stops every paid path. Set ``ai_trial_enabled=true`` and a
    # positive ``ai_trial_cost_micros`` to add a lifetime ceiling as well.
    ai_trial_enabled: bool = False
    ai_trial_requests: int = Field(default=1000000, ge=1)
    ai_trial_tokens: int = Field(default=1000000000, ge=1)
    ai_trial_cost_micros: int = Field(default=0, ge=0)
    ai_global_requests: int = Field(default=200, ge=1)
    ai_global_tokens: int = Field(default=500000, ge=1)
    ai_global_cost_micros: int = Field(default=1000000, ge=1)
    ai_user_requests: int = Field(default=20, ge=1)
    ai_user_tokens: int = Field(default=500000, ge=1)
    ai_user_cost_micros: int = Field(default=1000000, ge=1)
    ai_session_requests: int = Field(default=10, ge=1)
    ai_session_tokens: int = Field(default=250000, ge=1)
    ai_session_cost_micros: int = Field(default=500000, ge=1)
    ai_question_only: bool = True
    ai_provider: str = ""
    ai_model: str = "gpt-4o-mini"
    # Legacy challenge code may request a model id from an older provider. Each id
    # listed here is accepted from a candidate and mapped to ``ai_model`` before any
    # paid call. Empty (the default) accepts only the models a challenge declares,
    # so no vendor is assumed. Example: "gpt-4o,gpt-4o-mini".
    ai_model_aliases: str = ""
    ai_base_url: str = ""
    ai_api_key: str = ""
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
    execution_broker_url: str = ""
    execution_broker_ca_file: str = ""
    execution_broker_mode: bool = False
    broker_node_image: str = ""
    broker_python_image: str = ""

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
    domain: str = Field(default="", validation_alias=AliasChoices(
        "DOMAIN", "PROMPTCODE_DOMAIN", "domain"))
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
        if self.execution_broker_mode:
            # The daemon host is a separate role with no application credentials.
            if any((self.jwt_secret, self.grading_signing_key, self.openai_api_key,
                    self.deepseek_api_key, self.ai_api_key, self.smtp_password,
                    self.metrics_token, self.interview_internal_token)) or self.database_url != _DEFAULT_DATABASE_URL:
                raise ValueError("Execution broker must not receive database, JWT, signing or provider credentials.")
            self.sandbox_executor_token = self.sandbox_executor_token.strip()
            if len(self.sandbox_executor_token.encode()) < 32 or _looks_like_placeholder(self.sandbox_executor_token):
                raise ValueError("Execution broker requires a separate management token of at least 32 bytes.")
            return self
        self.execution_broker_url = self.execution_broker_url.strip().rstrip("/")
        if self.execution_broker_url:
            broker_url = urlparse(self.execution_broker_url)
            if (broker_url.scheme not in {"http", "https"} or not broker_url.hostname
                    or broker_url.username or broker_url.password or broker_url.query or broker_url.fragment):
                errors.append("PROMPTCODE_EXECUTION_BROKER_URL must be an HTTP(S) URL without credentials, query or fragment.")
            if self.environment.lower() == "production" and broker_url.scheme != "https":
                errors.append("Production execution broker requires HTTPS.")
            if len(self.sandbox_executor_token.strip().encode()) < 32:
                errors.append("Execution broker requires PROMPTCODE_SANDBOX_EXECUTOR_TOKEN of at least 32 bytes.")
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
        self.openai_base_url = str(self.openai_base_url or "").strip()
        self.ai_base_url = str(self.ai_base_url or "").strip()
        # Provider-agnostic resolution: the effective runtime credentials are the
        # ones belonging to the selected provider. A key configured for one vendor
        # is never paired with another vendor's base URL, which is the property the
        # previous DeepSeek-only assignment existed to guarantee.
        provider, effective_key, effective_base, _model, key_env = resolve_ai_credentials(self)
        if (provider in _KNOWN_PROVIDER_BASE_URLS and self.ai_base_url
                and not _provider_host_matches(provider, self.ai_base_url)):
            # Not fatal: resolve_ai_credentials already refused to pair this provider's
            # key with the other vendor's endpoint and fell back to the canonical one,
            # so the credential cannot leak. A stale PROMPTCODE_AI_BASE_URL left over
            # from a previous provider is common and must not stop the app from
            # starting, but it is worth surfacing.
            logging.getLogger(__name__).warning(
                "PROMPTCODE_AI_BASE_URL (%s) does not belong to AI provider %r; using %s instead.",
                self.ai_base_url, provider, effective_base,
            )
        self.ai_provider = provider
        self.openai_api_key = effective_key
        if effective_base:
            self.openai_base_url = effective_base
        if not self.debug:
            if not self.domain:
                errors.append("DOMAIN must be set when PROMPTCODE_DEBUG is false.")
            elif _is_localhost_domain(self.domain):
                errors.append("DOMAIN must not point at localhost when PROMPTCODE_DEBUG is false.")
            if not self.openai_api_key:
                errors.append(f"{key_env} must be set when PROMPTCODE_DEBUG is false.")
            elif (self.openai_api_key.lower().startswith("sk-placeholder")
                  or _looks_like_placeholder(self.openai_api_key)):
                errors.append(
                    f"{key_env} must be changed from a placeholder value when PROMPTCODE_DEBUG is false."
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
        if self.database_command_timeout_seconds <= self.database_pool_timeout_seconds:
            errors.append(
                "PROMPTCODE_DATABASE_COMMAND_TIMEOUT_SECONDS must exceed "
                "PROMPTCODE_DATABASE_POOL_TIMEOUT_SECONDS, otherwise a transaction "
                "queued behind the pool is killed mid-statement."
            )
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
        self.execution_backend = str(self.execution_backend or "").strip().lower()
        if self.execution_backend not in {"docker", "modal"}:
            errors.append("PROMPTCODE_EXECUTION_BACKEND must be 'docker' or 'modal'.")
        if self.modal_sandbox_timeout_seconds < 5:
            errors.append("PROMPTCODE_MODAL_SANDBOX_TIMEOUT_SECONDS must be at least 5.")
        if self.modal_sandbox_memory_mb < 128:
            errors.append("PROMPTCODE_MODAL_SANDBOX_MEMORY_MB must be at least 128.")
        if self.modal_sandbox_cpu <= 0:
            errors.append("PROMPTCODE_MODAL_SANDBOX_CPU must be positive.")
        if self.execution_backend == "modal":
            if not (self.modal_sandbox_image_node and self.modal_sandbox_image_python):
                errors.append(
                    "PROMPTCODE_MODAL_SANDBOX_IMAGE_NODE and PROMPTCODE_MODAL_SANDBOX_IMAGE_PYTHON "
                    "must both be set when PROMPTCODE_EXECUTION_BACKEND=modal."
                )
        self.storage_backend = str(self.storage_backend or "").strip().lower()
        if self.storage_backend not in {"filesystem", "supabase"}:
            errors.append("PROMPTCODE_STORAGE_BACKEND must be 'filesystem' or 'supabase'.")
        self.supabase_url = str(self.supabase_url or "").strip().rstrip("/")
        self.supabase_storage_bucket = str(self.supabase_storage_bucket or "").strip()
        if self.storage_backend == "supabase":
            supabase = urlparse(self.supabase_url)
            if supabase.scheme != "https" or not supabase.hostname:
                errors.append("PROMPTCODE_SUPABASE_URL must be an https project URL when PROMPTCODE_STORAGE_BACKEND=supabase.")
            if not str(self.supabase_service_role_key or "").strip():
                errors.append("PROMPTCODE_SUPABASE_SERVICE_ROLE_KEY must be set when PROMPTCODE_STORAGE_BACKEND=supabase.")
            if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{1,62}", self.supabase_storage_bucket):
                errors.append("PROMPTCODE_SUPABASE_STORAGE_BUCKET must be a valid bucket name.")
            if self.supabase_max_object_bytes > 50 * 1024 * 1024:
                errors.append(
                    "PROMPTCODE_SUPABASE_MAX_OBJECT_BYTES must not exceed 50 MB, the Supabase free-plan per-object limit."
                )
        if not self.debug:
            # Managed deployments must not depend on a self-managed host. Whether a
            # Docker backend has the runner it needs is a deployment requirement and
            # is enforced by app.core.startup_security.validate_production_startup.
            if self.execution_backend == "modal" and self.allow_unsafe_local_runner:
                errors.append("PROMPTCODE_EXECUTION_BACKEND=modal must not allow the unsafe local runner.")
        if errors:
            raise ValueError("Invalid PromptCode environment:\n- " + "\n- ".join(dict.fromkeys(errors)))
        return self


@lru_cache
def get_settings() -> Settings:
    # A broker must never load the app's repository .env by accident.
    if os.environ.get("PROMPTCODE_EXECUTION_BROKER_MODE", "").strip().lower() in {"1", "true", "yes", "on"}:
        return Settings(_env_file=None)  # type: ignore[call-arg]  # BaseSettings runtime-only keyword
    return Settings()
