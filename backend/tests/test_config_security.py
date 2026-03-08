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

    assert "placeholder or development default" in str(exc_info.value)


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
        openai_api_key="sk-live-test-key",
        domain="api.example.com",
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
            openai_api_key="sk-live-test-key",
            domain="api.example.com",
        )

    assert "PROMPTCODE_DATABASE_URL must be changed" in str(exc_info.value)


def test_settings_reject_insecure_production_sandbox_token():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=False,
            jwt_secret="prod-secret-with-real-entropy",
            database_url="postgresql+asyncpg://user:pass@db.example.com:5432/promptcode",
            openai_api_key="sk-live-test-key",
            domain="api.example.com",
            sandbox_executor_url="http://sandbox-executor:8090",
            sandbox_executor_token="local-sandbox-executor-token",
        )

    assert "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN must be changed" in str(exc_info.value)


def test_settings_collect_missing_and_placeholder_production_values():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=False,
            jwt_secret="replace-this-with-a-long-random-secret",
            database_url="postgresql+asyncpg://promptcode:promptcode@localhost:5432/promptcode",
            openai_api_key="sk-placeholder-test-key",
            domain="",
            sandbox_executor_url="http://sandbox-executor:8090",
            sandbox_executor_token="replace-this-with-a-random-secret",
        )

    error_text = str(exc_info.value)
    assert "PROMPTCODE_JWT_SECRET must be changed" in error_text
    assert "PROMPTCODE_DATABASE_URL must be changed" in error_text
    assert "PROMPTCODE_OPENAI_API_KEY must be changed" in error_text
    assert "DOMAIN must be set" in error_text
    assert "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN must be changed" in error_text


@pytest.mark.parametrize("domain", ["localhost", "127.0.0.1", "localhost:443"])
def test_settings_reject_localhost_domain_in_production(domain: str):
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=False,
            jwt_secret="prod-secret-with-real-entropy",
            database_url="postgresql+asyncpg://user:pass@db.example.com:5432/promptcode",
            openai_api_key="sk-live-test-key",
            domain=domain,
        )

    assert "DOMAIN must not point at localhost" in str(exc_info.value)


def test_settings_reject_valid_looking_placeholder_openai_key():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=False,
            jwt_secret="prod-secret-with-real-entropy",
            database_url="postgresql+asyncpg://user:pass@db.example.com:5432/promptcode",
            openai_api_key="sk-placeholder-prod-key-looks-real",
            domain="api.example.com",
        )

    assert "PROMPTCODE_OPENAI_API_KEY must be changed" in str(exc_info.value)


def test_settings_names_single_specific_invalid_placeholder_var():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=False,
            jwt_secret="prod-secret-with-real-entropy",
            database_url="postgresql+asyncpg://user:pass@db.example.com:5432/promptcode",
            openai_api_key="sk-live-test-key",
            domain="api.example.com",
            sandbox_executor_url="http://sandbox-executor:8090",
            sandbox_executor_token="replace-this-with-a-random-secret",
        )

    error_text = str(exc_info.value)
    assert "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN must be changed" in error_text
    assert "PROMPTCODE_JWT_SECRET must be changed" not in error_text
    assert "PROMPTCODE_OPENAI_API_KEY must be changed" not in error_text


def test_settings_lists_all_invalid_values_in_one_exception():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=False,
            jwt_secret="replace-this-with-a-long-random-secret",
            database_url="postgresql+asyncpg://promptcode:promptcode@localhost:5432/promptcode",
            openai_api_key="sk-placeholder-prod-key-looks-real",
            domain="127.0.0.1",
            sandbox_executor_url="http://sandbox-executor:8090",
            sandbox_executor_token="replace-this-with-a-random-secret",
        )

    error_text = str(exc_info.value)
    assert "PROMPTCODE_JWT_SECRET must be changed" in error_text
    assert "PROMPTCODE_DATABASE_URL must be changed" in error_text
    assert "PROMPTCODE_OPENAI_API_KEY must be changed" in error_text
    assert "DOMAIN must not point at localhost" in error_text
    assert "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN must be changed" in error_text


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


def test_settings_reject_invalid_auth_trusted_proxy_cidr():
    with pytest.raises(ValidationError) as exc_info:
        Settings(
            debug=True,
            jwt_secret="local-dev-secret-change-in-production",
            auth_trusted_proxy_cidrs=["not-a-cidr"],
        )

    assert "PROMPTCODE_AUTH_TRUSTED_PROXY_CIDRS" in str(exc_info.value)
