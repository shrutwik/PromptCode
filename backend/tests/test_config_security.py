from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_settings_require_jwt_secret():
    with pytest.raises(ValidationError) as exc_info:
        Settings(jwt_secret="", debug=True)

    assert "PROMPTCODE_JWT_SECRET must be set" in str(exc_info.value)


def test_settings_reject_insecure_production_secret():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=False,
            jwt_secret="local-dev-secret-change-in-production",
        )

    assert "must be changed from the development default" in str(exc_info.value)


def test_settings_allow_explicit_dev_secret_in_debug():
    settings = Settings(
        debug=True,
        jwt_secret="local-dev-secret-change-in-production",
    )

    assert settings.jwt_secret == "local-dev-secret-change-in-production"


def test_settings_allow_non_default_secret_in_production():
    settings = Settings(
        debug=False,
        jwt_secret="prod-secret-with-real-entropy",
        database_url="postgresql+asyncpg://user:pass@db.example.com:5432/promptcode",
    )

    assert settings.jwt_secret == "prod-secret-with-real-entropy"


def test_settings_reject_worker_timeout_shorter_than_interval():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=True,
            jwt_secret="local-dev-secret-change-in-production",
            worker_heartbeat_interval_seconds=10,
            worker_heartbeat_timeout_seconds=5,
        )

    assert "WORKER_HEARTBEAT_TIMEOUT_SECONDS" in str(exc_info.value)


def test_settings_require_sandbox_executor_token_when_url_is_configured():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=True,
            jwt_secret="local-dev-secret-change-in-production",
            sandbox_executor_url="http://sandbox-executor:8090",
        )

    assert "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN" in str(exc_info.value)


def test_settings_reject_insecure_production_database_url():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=False,
            jwt_secret="prod-secret-with-real-entropy",
            database_url="postgresql+asyncpg://promptcode:promptcode@localhost:5432/promptcode",
        )

    assert "PROMPTCODE_DATABASE_URL must be changed" in str(exc_info.value)


def test_settings_reject_insecure_production_sandbox_token():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=False,
            jwt_secret="prod-secret-with-real-entropy",
            database_url="postgresql+asyncpg://user:pass@db.example.com:5432/promptcode",
            sandbox_executor_url="http://sandbox-executor:8090",
            sandbox_executor_token="local-sandbox-executor-token",
        )

    assert "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN must be changed" in str(exc_info.value)


def test_settings_require_positive_scaling_limits():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=True,
            jwt_secret="local-dev-secret-change-in-production",
            evaluation_max_parallel_specs=0,
        )

    assert "PROMPTCODE_EVALUATION_MAX_PARALLEL_SPECS" in str(exc_info.value)

    with pytest.raises(ValidationError) as sandbox_exc:
        Settings(
            debug=True,
            jwt_secret="local-dev-secret-change-in-production",
            sandbox_executor_max_concurrent_runs=0,
        )

    assert "PROMPTCODE_SANDBOX_EXECUTOR_MAX_CONCURRENT_RUNS" in str(sandbox_exc.value)
