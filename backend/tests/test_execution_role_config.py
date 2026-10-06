"""The daemon role must not load or accept application credentials."""
import pytest
from pydantic import ValidationError
from app.core.config import Settings, get_settings

TOKEN = "execution-management-token-32-bytes-minimum"


@pytest.fixture(autouse=True)
def clear_app_credentials(monkeypatch):
    for name in ("PROMPTCODE_JWT_SECRET", "PROMPTCODE_DATABASE_URL", "PROMPTCODE_GRADING_SIGNING_KEY",
                 "PROMPTCODE_OPENAI_API_KEY", "OPENAI_API_KEY", "DEEPSEEK_API_KEY", "PROMPTCODE_DEEPSEEK_API_KEY",
                 "PROMPTCODE_AI_API_KEY", "PROMPTCODE_METRICS_TOKEN", "PROMPTCODE_INTERVIEW_INTERNAL_TOKEN",
                 "PROMPTCODE_SMTP_PASSWORD"):
        monkeypatch.delenv(name, raising=False)


def broker(**kwargs):
    return Settings(_env_file=None, execution_broker_mode=True,
                    sandbox_executor_token=TOKEN, **kwargs)


def test_broker_role_needs_no_app_database_jwt_or_provider():
    settings = broker(environment="production")
    assert not settings.jwt_secret
    assert not settings.deepseek_api_key
    assert not settings.grading_signing_key


@pytest.mark.parametrize("field,value", [
    ("database_url", "postgresql+asyncpg://real:credentials@app-db/database"),
    ("jwt_secret", "application-secret"),
    ("grading_signing_key", "application-signing-key"),
    ("deepseek_api_key", "provider-key"),
    ("openai_api_key", "legacy-provider-key"),
    ("ai_api_key", "assistant-key"),
    ("smtp_password", "mail-secret"),
    ("metrics_token", "metrics-secret"),
    ("interview_internal_token", "internal-app-secret"),
])
def test_broker_rejects_application_credentials(field, value):
    with pytest.raises(ValidationError, match="must not receive"):
        broker(**{field: value})


def test_broker_get_settings_never_reads_app_env(monkeypatch, tmp_path):
    dotenv = tmp_path / "application.env"
    dotenv.write_text("PROMPTCODE_JWT_SECRET=secret-from-app-file\nDEEPSEEK_API_KEY=provider-key\n")
    monkeypatch.setitem(Settings.model_config, "env_file", str(dotenv))
    monkeypatch.setenv("PROMPTCODE_EXECUTION_BROKER_MODE", "true")
    monkeypatch.setenv("PROMPTCODE_SANDBOX_EXECUTOR_TOKEN", TOKEN)
    for name in ("PROMPTCODE_JWT_SECRET", "DEEPSEEK_API_KEY", "PROMPTCODE_OPENAI_API_KEY",
                 "PROMPTCODE_DATABASE_URL", "PROMPTCODE_GRADING_SIGNING_KEY", "PROMPTCODE_AI_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    get_settings.cache_clear()
    try:
        assert get_settings().jwt_secret == ""
    finally:
        get_settings.cache_clear()


@pytest.mark.parametrize("url", ["http://broker.example.com", "https://user:pass@broker.example.com",
                                 "https://broker.example.com?secret=value", "file:///var/run/docker.sock"])
def test_app_rejects_unsafe_production_broker_url(url):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, debug=True, jwt_secret="test-app-secret",
                 environment="production", execution_broker_url=url,
                 sandbox_executor_token=TOKEN)


def test_broker_short_management_secret_rejected():
    with pytest.raises(ValidationError, match="management token"):
        Settings(_env_file=None, execution_broker_mode=True, sandbox_executor_token="short")
