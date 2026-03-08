from __future__ import annotations

import subprocess
from pathlib import Path

from app.db.types import JSONType
from app.models.challenge import Challenge


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATE_ENV_SCRIPT = REPO_ROOT / "scripts" / "validate-env.sh"


def _write(path: Path, content: str) -> Path:
    path.write_text(content, encoding="utf-8")
    return path


def _run_validate_env(tmp_path: Path, *, env_text: str, compose_text: str, config_text: str):
    env_file = _write(tmp_path / ".env.example", env_text)
    compose_file = _write(tmp_path / "docker-compose.yml", compose_text)
    config_file = _write(tmp_path / "config.py", config_text)
    return subprocess.run(
        [
            "bash",
            str(VALIDATE_ENV_SCRIPT),
            "--env-file",
            str(env_file),
            "--config-file",
            str(config_file),
            "--compose-file",
            str(compose_file),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_validate_env_script_rejects_missing_required_compose_var(tmp_path: Path):
    result = _run_validate_env(
        tmp_path,
        env_text="PROMPTCODE_JWT_SECRET=test-secret\n",
        compose_text="services:\n  backend:\n    environment:\n      PROMPTCODE_DB_PASSWORD: ${PROMPTCODE_DB_PASSWORD:?set PROMPTCODE_DB_PASSWORD}\n",
        config_text="class Settings:\n    jwt_secret: str = ''\n",
    )

    assert result.returncode == 1
    assert "PROMPTCODE_DB_PASSWORD" in result.stderr


def test_validate_env_script_rejects_dead_env_var(tmp_path: Path):
    result = _run_validate_env(
        tmp_path,
        env_text="PROMPTCODE_JWT_SECRET=test-secret\nUNUSED_VAR=value\n",
        compose_text="services:\n  backend:\n    environment:\n      PROMPTCODE_JWT_SECRET: ${PROMPTCODE_JWT_SECRET:?set PROMPTCODE_JWT_SECRET}\n",
        config_text="class Settings:\n    jwt_secret: str = ''\n",
    )

    assert result.returncode == 1
    assert "UNUSED_VAR" in result.stderr


def test_challenge_tags_column_uses_json_contract():
    assert isinstance(Challenge.__table__.c.tags.type, JSONType)
