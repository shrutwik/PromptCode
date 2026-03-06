from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import model_validator
from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"
_INSECURE_JWT_SECRETS = {
    "",
    "change-me-in-production-use-a-real-secret-key",
    "local-dev-secret-change-in-production",
}


class Settings(BaseSettings):
    app_name: str = "PromptCode"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://promptcode:promptcode@localhost:5432/promptcode"
    database_echo: bool = False
    # Set True when using Supabase or any hosted Postgres that requires SSL
    database_ssl_require: bool = False
    # Optional CA bundle path for verified TLS connections.
    database_ssl_ca_file: str = ""

    openai_api_key: str = ""
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

    evaluation_normal_runs: int = 5
    evaluation_adversarial_runs: int = 2
    evaluation_job_timeout_seconds: int = 1800
    submission_inline_queue_processing: bool = True

    jwt_secret: str = ""

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    model_config = {"env_prefix": "PROMPTCODE_", "env_file": str(_ENV_FILE)}

    @model_validator(mode="after")
    def validate_security_settings(self) -> "Settings":
        secret = str(self.jwt_secret or "").strip()
        if not secret:
            raise ValueError("PROMPTCODE_JWT_SECRET must be set.")
        self.jwt_secret = secret
        if not self.debug and secret in _INSECURE_JWT_SECRETS:
            raise ValueError(
                "PROMPTCODE_JWT_SECRET must be changed from the development default when PROMPTCODE_DEBUG is false."
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
