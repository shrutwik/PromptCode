from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings

_ENV_FILE = Path(__file__).resolve().parent.parent.parent.parent / ".env"


class Settings(BaseSettings):
    app_name: str = "PromptCode"
    debug: bool = False

    database_url: str = "postgresql+asyncpg://promptcode:promptcode@localhost:5432/promptcode"
    database_echo: bool = False

    openai_api_key: str = ""
    openai_base_url: str = ""
    openai_model: str = "gpt-4o"

    sandbox_image: str = "promptcode-sandbox:latest"
    sandbox_timeout_seconds: int = 120
    sandbox_memory_limit: str = "512m"
    sandbox_cpu_limit: float = 1.0

    evaluation_normal_runs: int = 5
    evaluation_adversarial_runs: int = 2

    jwt_secret: str = "change-me-in-production-use-a-real-secret-key"

    cors_origins: list[str] = [
        "http://localhost:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ]

    model_config = {"env_prefix": "PROMPTCODE_", "env_file": str(_ENV_FILE)}


@lru_cache
def get_settings() -> Settings:
    return Settings()
