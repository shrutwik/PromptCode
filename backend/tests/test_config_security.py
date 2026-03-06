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
    )

    assert settings.jwt_secret == "prod-secret-with-real-entropy"
