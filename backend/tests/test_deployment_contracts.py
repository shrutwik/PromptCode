from __future__ import annotations

import gzip
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import Column, Index, MetaData, String, Table, UniqueConstraint, types
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect

from app.db.alembic_compare import compare_type, should_include_object
from app.db.types import GUID, JSONType
from app.models.challenge import Challenge
from app.models.evaluation_job import EvaluationJob

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATE_ENV_SCRIPT = REPO_ROOT / "scripts" / "validate-env.sh"
CHECK_PROD_HEALTH_SCRIPT = REPO_ROOT / "scripts" / "check-prod-health.sh"
BACKUP_DB_SCRIPT = REPO_ROOT / "scripts" / "backup-db.sh"
RESTORE_DB_SCRIPT = REPO_ROOT / "scripts" / "restore-db.sh"
SETUP_GHCR_LOGIN_SCRIPT = REPO_ROOT / "scripts" / "setup-ghcr-login.sh"
VALIDATE_HOST_ENV_SCRIPT = REPO_ROOT / "scripts" / "validate-host-env.sh"
VALIDATE_PROD_HOST_SCRIPT = REPO_ROOT / "scripts" / "validate-prod-host.sh"
BACKEND_CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "backend-ci.yml"
OPS_REHEARSALS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "ops-rehearsals.yml"
DOCKERFILE_BACKEND = REPO_ROOT / "docker" / "Dockerfile.backend"
DOCKERFILE_SANDBOX = REPO_ROOT / "docker" / "Dockerfile.sandbox"
DOCKER_COMPOSE_BASE = REPO_ROOT / "docker-compose.yml"
DOCKER_COMPOSE_PROD = REPO_ROOT / "docker-compose.prod.yml"
DEPENDABOT_CONFIG = REPO_ROOT / ".github" / "dependabot.yml"


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


def _run_validate_host_env(tmp_path: Path, env_text: str):
    deploy_dir = tmp_path / "deploy"
    deploy_dir.mkdir(parents=True, exist_ok=True)
    _write(deploy_dir / ".env", env_text)
    return subprocess.run(
        ["bash", str(VALIDATE_HOST_ENV_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        env={**os.environ, "DEPLOY_DIR": str(deploy_dir)},
    )


def _run_setup_ghcr_login(tmp_path: Path, env_text: str):
    deploy_dir = tmp_path / "deploy"
    fake_bin = tmp_path / "bin"
    capture_path = tmp_path / "ghcr-login.txt"
    deploy_dir.mkdir(parents=True)
    fake_bin.mkdir(parents=True)
    _write(deploy_dir / ".env", env_text)
    _write(
        fake_bin / "docker",
        """#!/usr/bin/env bash
set -euo pipefail
printf '%s|%s|' "$*" "${FAKE_GHCR_CAPTURE}" > "${FAKE_GHCR_CAPTURE}"
cat >> "${FAKE_GHCR_CAPTURE}"
""",
    )
    (fake_bin / "docker").chmod(0o755)
    return subprocess.run(
        ["bash", str(SETUP_GHCR_LOGIN_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "DEPLOY_DIR": str(deploy_dir),
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
            "FAKE_GHCR_CAPTURE": str(capture_path),
        },
    ), capture_path


def _run_validate_prod_host(
    tmp_path: Path,
    *,
    include_rclone: bool = True,
    include_caddyfile: bool = True,
    include_seed_script: bool = True,
    include_cleanup_script: bool = True,
    cron_entries: str = "",
):
    deploy_dir = tmp_path / "deploy"
    fake_bin = tmp_path / "bin"
    deploy_scripts = deploy_dir / "scripts"
    deploy_docker = deploy_dir / "docker"
    deploy_scripts.mkdir(parents=True)
    deploy_docker.mkdir(parents=True)
    fake_bin.mkdir(parents=True)
    _write(
        deploy_dir / ".env",
        "\n".join(
            [
                "DOMAIN=api.example.com",
                "PROMPTCODE_DB_PASSWORD=prod-db-password",
                "PROMPTCODE_JWT_SECRET=prod-jwt-secret-0123456789abcdef",
                "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=prod-sandbox-secret-0123456789-extra-bytes",
                "PROMPTCODE_EXECUTION_BROKER_URL=https://execution.example.com",
                "PROMPTCODE_GRADING_SIGNING_KEY=test-signing-key-32bytes-minimum-value",
                "PROMPTCODE_INTERVIEW_INTERNAL_TOKEN=test-internal-token-32bytes-minimum",
                "PROMPTCODE_OPENAI_API_KEY=sk-live-prod-key",
                "PROMPTCODE_METRICS_TOKEN=metrics-secret",
                "RCLONE_REMOTE=s3:promptcode/backups",
                "GHCR_USERNAME=promptcode-bot",
                "GHCR_TOKEN=ghp_example_token",
                "",
            ],
        ),
    )
    _write(deploy_dir / "docker-compose.yml", "services: {}\n")
    _write(deploy_dir / "docker-compose.prod.yml", "services: {}\n")
    if include_caddyfile:
        _write(
            deploy_docker / "Caddyfile.prod",
            (REPO_ROOT / "docker" / "Caddyfile.prod").read_text(encoding="utf-8"),
        )
    for script_path in (
        "backup-db.sh",
        "restore-db.sh",
        "seed-prod-data.sh",
        "check-prod-health.sh",
        "cleanup-interview.sh",
        "validate-host-env.sh",
        "setup-ghcr-login.sh",
    ):
        if script_path == "seed-prod-data.sh" and not include_seed_script:
            continue
        if script_path == 'cleanup-interview.sh' and not include_cleanup_script:
            continue
        target = deploy_scripts / script_path
        target.write_text((REPO_ROOT / "scripts" / script_path).read_text(encoding="utf-8"), encoding="utf-8")
        target.chmod(0o755)
    _write(
        fake_bin / "docker",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == "info" ]]; then
  exit 0
elif [[ "$*" == "compose version" ]]; then
  echo "Docker Compose version v2.24.0"
else
  echo "unexpected docker invocation: $*" >&2
  exit 1
fi
""",
    )
    if include_rclone:
        _write(
            fake_bin / "rclone",
            "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
        )
        (fake_bin / "rclone").chmod(0o755)
    _write(
        fake_bin / "crontab",
        f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "-l" ]]; then
  printf '%s' {cron_entries!r}
else
  echo "unexpected crontab invocation: $*" >&2
  exit 1
fi
""",
    )
    for path in fake_bin.iterdir():
        path.chmod(0o755)

    return subprocess.run(
        ["bash", str(VALIDATE_PROD_HOST_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        env={
            **os.environ,
            "DEPLOY_DIR": str(deploy_dir),
            "PATH": f"{fake_bin}:{os.environ['PATH']}",
        },
    )


def _run_bootstrap_prod_host(
    tmp_path: Path,
    *,
    ufw_active: bool,
    allow_external_firewall: bool = False,
    include_rclone: bool = True,
):
    deploy_dir = tmp_path / "deploy"
    fake_bin = tmp_path / "bin"
    cron_file = tmp_path / "crontab.txt"
    fake_bin.mkdir(parents=True)

    _write(
        fake_bin / "docker",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$*" == "--version" ]]; then
  echo "Docker version 26.1.0"
elif [[ "$*" == "compose version" ]]; then
  echo "Docker Compose version v2.24.0"
elif [[ "$*" == "info" ]]; then
  exit 0
else
  echo "unexpected docker invocation: $*" >&2
  exit 1
fi
""",
    )
    _write(
        fake_bin / "ufw",
        f"""#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "status" ]]; then
  echo "Status: {'active' if ufw_active else 'inactive'}"
elif [[ "$1" == "allow" ]]; then
  exit 0
else
  echo "unexpected ufw invocation: $*" >&2
  exit 1
fi
""",
    )
    _write(
        fake_bin / "groups",
        """#!/usr/bin/env bash
set -euo pipefail
echo "tester : tester docker"
""",
    )
    if include_rclone:
        _write(
            fake_bin / "rclone",
            "#!/usr/bin/env bash\nset -euo pipefail\nexit 0\n",
        )
    _write(
        fake_bin / "crontab",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "-l" ]]; then
  if [[ -f "${FAKE_CRON_FILE}" ]]; then
    cat "${FAKE_CRON_FILE}"
    exit 0
  fi
  exit 1
fi
cat > "${FAKE_CRON_FILE}"
""",
    )
    for path in fake_bin.iterdir():
        path.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["DEPLOY_DIR"] = str(deploy_dir)
    env["FAKE_CRON_FILE"] = str(cron_file)
    env["FAKE_BIN_DIR"] = str(fake_bin)
    if allow_external_firewall:
        env["PROMPTCODE_ALLOW_EXTERNAL_FIREWALL"] = "1"

    result = subprocess.run(
        ["bash", str(REPO_ROOT / "scripts" / "bootstrap-prod-host.sh")],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return result, deploy_dir


def _run_check_prod_health(
    tmp_path: Path,
    *,
    metrics_status: str = "200",
    heartbeat_age: str = "5",
    queue_depth: str = "0",
    backup_age_seconds: int = 300,
    last_deploy_status: str = "success 123 abcdef",
    capture_mktemp: bool = False,
    grading_failed: str = '0',
    grading_stale: str = '0',
    grading_queue_age: str = '0',
):
    deploy_dir = tmp_path / "deploy"
    backups_dir = deploy_dir / "backups"
    fake_bin = tmp_path / "bin"
    docker_path = fake_bin / "docker"

    backups_dir.mkdir(parents=True)
    fake_bin.mkdir(parents=True)
    _write(deploy_dir / "docker-compose.yml", "services: {}\n")
    _write(deploy_dir / "docker-compose.prod.yml", "services: {}\n")
    _write(deploy_dir / ".last-deploy-status", f"{last_deploy_status}\n")
    _write(
        backups_dir / "last-successful-backup.txt",
        f"{int(time.time()) - backup_age_seconds}\n",
    )
    _write(
        backups_dir / ".last-success-timestamp",
        f"{int(time.time()) - backup_age_seconds}\n",
    )
    _write(
        docker_path,
        """#!/usr/bin/env bash
set -euo pipefail
cmd="$*"
if [[ "$cmd" == *"/metrics"* ]]; then
  printf '%s\\n' "${FAKE_METRICS_STATUS}"
elif [[ "$cmd" == *"worker_heartbeats"* ]]; then
  printf '%s\\n' "${FAKE_HEARTBEAT_AGE}"
elif [[ "$cmd" == *"evaluation_jobs"* ]]; then
  printf '%s\\n' "${FAKE_QUEUE_DEPTH}"
elif [[ "$cmd" == *"interview_grading_jobs"* ]]; then
  if [[ "$cmd" == *"status='failed'"* ]]; then printf '%s\\n' "${FAKE_GRADING_FAILED}";
  elif [[ "$cmd" == *"lease_expires_at"* ]]; then printf '%s\\n' "${FAKE_GRADING_STALE}";
  elif [[ "$cmd" == *"MIN(created_at)"* ]]; then printf '%s\\n' "${FAKE_GRADING_QUEUE_AGE}";
  else printf '0\\n'; fi
else
  echo "unexpected docker invocation: $cmd" >&2
  exit 1
fi
""",
    )
    docker_path.chmod(0o755)
    metrics_status_file = tmp_path / "metrics-status.txt"
    if capture_mktemp:
        mktemp_path = fake_bin / "mktemp"
        _write(
            mktemp_path,
            f"""#!/usr/bin/env bash
set -euo pipefail
: > {str(metrics_status_file)!r}
printf '%s\\n' {str(metrics_status_file)!r}
""",
        )
        mktemp_path.chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["DEPLOY_DIR"] = str(deploy_dir)
    env["FAKE_METRICS_STATUS"] = metrics_status
    env["FAKE_HEARTBEAT_AGE"] = heartbeat_age
    env["FAKE_QUEUE_DEPTH"] = queue_depth
    env['FAKE_GRADING_FAILED'] = grading_failed
    env['FAKE_GRADING_STALE'] = grading_stale
    env['FAKE_GRADING_QUEUE_AGE'] = grading_queue_age

    result = subprocess.run(
        ["bash", str(CHECK_PROD_HEALTH_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return result, metrics_status_file


def _prepare_operational_script_fixture(tmp_path: Path) -> tuple[Path, Path, Path]:
    deploy_dir = tmp_path / "deploy"
    backups_dir = deploy_dir / "backups"
    fake_bin = tmp_path / "bin"

    backups_dir.mkdir(parents=True)
    fake_bin.mkdir(parents=True)
    artifact_root = deploy_dir / 'artifacts'
    (artifact_root / '.submitted').mkdir(parents=True)
    _write(deploy_dir / "docker-compose.yml", "services: {}\n")
    _write(deploy_dir / "docker-compose.prod.yml", "services: {}\n")
    _write(
        deploy_dir / ".env",
        "\n".join(
            [
                "PROMPTCODE_DB_PASSWORD=test-db-password",
                "PROMPTCODE_DB_USER=test-user",
                "PROMPTCODE_DB_NAME=test-db",
                f"RCLONE_REMOTE={tmp_path / 'remote'}",
                f"BACKUP_ARTIFACT_ROOT={artifact_root}",
                "",
            ]
        ),
    )
    return deploy_dir, backups_dir, fake_bin


def _run_backup_db(
    tmp_path: Path,
    *,
    include_rclone: bool = True,
    set_rclone_remote: bool = True,
):
    deploy_dir, backups_dir, fake_bin = _prepare_operational_script_fixture(tmp_path)
    remote_dir = tmp_path / "remote"
    remote_dir.mkdir(parents=True, exist_ok=True)

    _write(
        fake_bin / "docker",
        """#!/usr/bin/env bash
set -euo pipefail
cmd="$*"
if [[ "$cmd" == *"pg_dump"* ]]; then
  printf 'CREATE TABLE backup_check (id integer);\\n'
else
  echo "unexpected docker invocation: $cmd" >&2
  exit 1
fi
""",
    )
    (fake_bin / "docker").chmod(0o755)

    if include_rclone:
        _write(
            fake_bin / "rclone",
            """#!/usr/bin/env bash
set -euo pipefail
cmd="$1"
shift
case "${cmd}" in
  copy)
    src="$1"
    dest="$2"
    mkdir -p "${dest}"
    cp "${src}" "${dest}/"
    ;;
  *)
    echo "unexpected rclone invocation: ${cmd}" >&2
    exit 1
    ;;
esac
""",
        )
        (fake_bin / "rclone").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["DEPLOY_DIR"] = str(deploy_dir)
    if not set_rclone_remote:
        env.pop("RCLONE_REMOTE", None)
        _write(
            deploy_dir / ".env",
            "\n".join(
                [
                    "PROMPTCODE_DB_PASSWORD=test-db-password",
                    "PROMPTCODE_DB_USER=test-user",
                    "PROMPTCODE_DB_NAME=test-db",
                    "",
                ]
            ),
        )

    result = subprocess.run(
        ["bash", str(BACKUP_DB_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return result, backups_dir, remote_dir


def _run_restore_db(
    tmp_path: Path,
    backup_ref: str,
    *,
    include_rclone: bool = True,
    set_rclone_remote: bool = True,
):
    deploy_dir, backups_dir, fake_bin = _prepare_operational_script_fixture(tmp_path)
    remote_dir = tmp_path / "remote"
    remote_dir.mkdir(parents=True, exist_ok=True)
    restore_capture = tmp_path / "restored.sql"

    _write(
        fake_bin / "docker",
        """#!/usr/bin/env bash
set -euo pipefail
cmd="$*"
if [[ "$cmd" == *" psql "* ]]; then
  cat > "${FAKE_RESTORE_CAPTURE}"
else
  echo "unexpected docker invocation: $cmd" >&2
  exit 1
fi
""",
    )
    (fake_bin / "docker").chmod(0o755)

    if include_rclone:
        _write(
            fake_bin / "rclone",
            """#!/usr/bin/env bash
set -euo pipefail
cmd="$1"
shift
case "${cmd}" in
  copyto)
    src="$1"
    dest="$2"
    mkdir -p "$(dirname "${dest}")"
    cp "${src}" "${dest}"
    ;;
  *)
    echo "unexpected rclone invocation: ${cmd}" >&2
    exit 1
    ;;
esac
""",
        )
        (fake_bin / "rclone").chmod(0o755)

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["DEPLOY_DIR"] = str(deploy_dir)
    env["BACKUP_DIR"] = str(backups_dir)
    env["FAKE_RESTORE_CAPTURE"] = str(restore_capture)
    if not set_rclone_remote:
        env.pop("RCLONE_REMOTE", None)
        _write(
            deploy_dir / ".env",
            "\n".join(
                [
                    "PROMPTCODE_DB_PASSWORD=test-db-password",
                    "PROMPTCODE_DB_USER=test-user",
                    "PROMPTCODE_DB_NAME=test-db",
                    "",
                ]
            ),
        )

    result = subprocess.run(
        ["bash", str(RESTORE_DB_SCRIPT), backup_ref],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )
    return result, restore_capture, backups_dir, remote_dir


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


def test_validate_env_script_allows_known_operational_env_vars(tmp_path: Path):
    result = _run_validate_env(
        tmp_path,
        env_text=(
            "PROMPTCODE_JWT_SECRET=test-secret\n"
            "RCLONE_REMOTE=s3:bucket/path\n"
            "PROMPTCODE_GHCR_PUBLIC_IMAGES=false\n"
            "GHCR_USERNAME=promptcode\n"
            "GHCR_TOKEN=ghp-secret\n"
        ),
        compose_text=(
            "services:\n"
            "  backend:\n"
            "    environment:\n"
            "      PROMPTCODE_JWT_SECRET: ${PROMPTCODE_JWT_SECRET:?set PROMPTCODE_JWT_SECRET}\n"
        ),
        config_text="class Settings:\n    jwt_secret: str = ''\n",
    )

    assert result.returncode == 0
    assert "Environment contract OK" in result.stdout


def test_challenge_tags_column_uses_json_contract():
    assert isinstance(Challenge.__table__.c.tags.type, JSONType)


def test_alembic_compare_treats_guid_wrapper_as_equivalent_to_baseline_varchar() -> None:
    assert compare_type(None, None, None, String(36), GUID()) is False
    assert compare_type(None, None, None, String(12), GUID()) is None


def test_guid_wrapper_stays_string_backed_on_postgresql_for_legacy_schema() -> None:
    guid = GUID()
    pg = postgresql_dialect()

    assert isinstance(guid.load_dialect_impl(pg), String)
    assert guid.process_bind_param(uuid.UUID("11111111-1111-1111-1111-111111111111"), pg) == (
        "11111111-1111-1111-1111-111111111111"
    )


def test_alembic_compare_treats_json_wrapper_as_equivalent_to_baseline_json() -> None:
    assert compare_type(None, None, None, types.JSON(), JSONType()) is False
    assert compare_type(None, None, None, types.Text(), JSONType()) is False


def test_alembic_compare_ignores_sqlite_leaderboard_unique_index_shape() -> None:
    table = Table(
        "leaderboard",
        MetaData(),
        Column("challenge_id", String(36)),
        Column("user_id", String(36)),
    )
    reflected_index = Index(
        "uq_leaderboard_challenge_user",
        table.c.challenge_id,
        table.c.user_id,
        unique=True,
    )
    metadata_constraint = UniqueConstraint(
        table.c.challenge_id,
        table.c.user_id,
        name="uq_leaderboard_challenge_user",
    )

    assert (
        should_include_object(
            "sqlite",
            reflected_index,
            reflected_index.name,
            "index",
            True,
            None,
        )
        is False
    )
    assert (
        should_include_object(
            "sqlite",
            metadata_constraint,
            metadata_constraint.name,
            "unique_constraint",
            False,
            None,
        )
        is False
    )
    assert (
        should_include_object(
            "postgresql",
            metadata_constraint,
            metadata_constraint.name,
            "unique_constraint",
            False,
            None,
        )
        is True
    )


def test_evaluation_job_submission_constraint_matches_baseline_schema() -> None:
    unique_constraints = {
        constraint.name
        for constraint in EvaluationJob.__table__.constraints
        if isinstance(constraint, UniqueConstraint)
    }
    submission_indexes = {
        index.name: index.unique for index in EvaluationJob.__table__.indexes
    }

    assert "uq_evaluation_jobs_submission_id" in unique_constraints
    assert submission_indexes["ix_evaluation_jobs_submission_id"] is False


def test_deploy_workflow_seeds_challenges_before_smoke() -> None:
    workflow_text = BACKEND_CI_WORKFLOW.read_text(encoding="utf-8")

    seed_step = "      - name: Seed production challenge data"
    smoke_step = "      - name: Post-deploy smoke test"

    assert seed_step in workflow_text
    assert "bash /opt/promptcode/scripts/seed-prod-data.sh" in workflow_text
    assert workflow_text.index(seed_step) < workflow_text.index(smoke_step)


def test_deploy_workflow_rollback_uses_previous_tag_without_build() -> None:
    workflow_text = BACKEND_CI_WORKFLOW.read_text(encoding="utf-8")

    assert "      - name: Roll back failed deploy" in workflow_text
    assert "steps.sync_host.outcome == 'success'" in workflow_text
    assert "steps.deploy_host.outcome == 'failure'" in workflow_text
    assert 'ROLLBACK_TAG="$(cat /opt/promptcode/.previous-image-tag)"' in workflow_text
    assert "bash /opt/promptcode/scripts/validate-host-env.sh" in workflow_text
    assert "bash /opt/promptcode/scripts/setup-ghcr-login.sh" in workflow_text
    assert 'docker pull ${{ env.IMAGE_NAME }}:${ROLLBACK_TAG}' in workflow_text
    assert 'docker pull ${{ env.SANDBOX_IMAGE_NAME }}:${ROLLBACK_TAG}' in workflow_text
    assert 'docker tag ${{ env.SANDBOX_IMAGE_NAME }}:${ROLLBACK_TAG} promptcode-sandbox:latest' in workflow_text
    assert (
        'IMAGE_TAG="$ROLLBACK_TAG" docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build'
        in workflow_text
    )
    assert 'echo "$ROLLBACK_TAG" > /opt/promptcode/.current-image-tag' in workflow_text
    assert "rolled_back %s %s" in workflow_text


def test_deploy_workflow_validates_host_env_and_refreshes_ghcr_before_pull() -> None:
    workflow_text = BACKEND_CI_WORKFLOW.read_text(encoding="utf-8")

    validate_step = "            bash /opt/promptcode/scripts/validate-prod-host.sh"
    ghcr_step = "            bash /opt/promptcode/scripts/setup-ghcr-login.sh"
    pull_step = "            docker pull ${{ env.IMAGE_NAME }}:${{ github.sha }}"

    assert validate_step in workflow_text
    assert ghcr_step in workflow_text
    assert pull_step in workflow_text
    assert workflow_text.index(validate_step) < workflow_text.index(pull_step)
    assert workflow_text.index(ghcr_step) < workflow_text.index(pull_step)
    assert "scripts/validate-prod-host.sh" in workflow_text


def test_deploy_workflow_uses_extended_ssh_connection_timeout() -> None:
    workflow_text = BACKEND_CI_WORKFLOW.read_text(encoding="utf-8")

    assert "      DEPLOY_SSH_TIMEOUT: 2m" in workflow_text
    assert workflow_text.count("timeout: ${{ env.DEPLOY_SSH_TIMEOUT }}") >= 6


def _load_compose_services(compose_text: str) -> dict[str, dict[str, list[str]]]:
    """Minimal service->volumes reader.

    The deployment files use custom YAML tags (``!reset``, ``!override``) that a
    plain loader rejects, so read only the top-level service blocks and their
    ``volumes:`` list items.
    """
    services: dict[str, dict[str, list[str]]] = {}
    current: str | None = None
    in_volumes = False
    for line in compose_text.splitlines():
        stripped = line.strip()
        indent = len(line) - len(line.lstrip())
        if indent == 2 and stripped.endswith(":") and not stripped.startswith("-"):
            current = stripped[:-1]
            services[current] = {"volumes": []}
            in_volumes = False
            continue
        if current is None:
            continue
        if indent == 4 and stripped == "volumes:":
            in_volumes = True
            continue
        if in_volumes:
            if indent >= 6 and stripped.startswith("- "):
                services[current]["volumes"].append(stripped[2:].split("#")[0].strip())
                continue
            if stripped and indent <= 4:
                in_volumes = False
    return services


def test_prod_compose_mounts_the_artifact_root_for_api_and_workers() -> None:
    """The API and every worker must share one host artifact path.

    The API writes candidate workspaces and immutable submissions; workers read
    the frozen snapshots to grade. If the API's configured root is not mounted,
    it resolves inside the container's ephemeral filesystem: submissions become
    invisible to workers and are lost on restart.
    """
    prod_compose = DOCKER_COMPOSE_PROD.read_text(encoding="utf-8")
    services = _load_compose_services(prod_compose)
    mount = "${PROMPTCODE_INTERVIEW_HOST_WORKDIR:-/var/promptcode/interview_workspaces}"
    backend_mounts = services["backend"]["volumes"]
    assert any(volume.startswith(mount + ":") for volume in backend_mounts), \
        "backend does not mount the artifact root"
    # The API is the only writer, so its mount must not be read-only.
    api_mount = next(volume for volume in backend_mounts if volume.startswith(mount + ":"))
    assert not api_mount.rstrip().endswith(":ro"), "backend must own read-write artifact storage"
    # Workers read the same path.
    for worker in ("worker", "worker-b"):
        assert any(volume.startswith(mount + ":") and volume.rstrip().endswith(":ro")
                   for volume in services[worker]["volumes"]), f"{worker} mount changed"
    assert "PROMPTCODE_INTERVIEW_WORKSPACE_ROOT" in prod_compose


def test_prod_compose_defaults_database_ssl_to_false_for_bundled_postgres() -> None:
    compose_text = DOCKER_COMPOSE_PROD.read_text(encoding="utf-8")

    assert 'PROMPTCODE_DATABASE_SSL_REQUIRE: ${PROMPTCODE_DATABASE_SSL_REQUIRE:-false}' in compose_text
    assert "PROMPTCODE_RUNNER: docker" in compose_text


def test_runtime_images_use_version_pinned_tags() -> None:
    backend_dockerfile = DOCKERFILE_BACKEND.read_text(encoding="utf-8")
    sandbox_dockerfile = DOCKERFILE_SANDBOX.read_text(encoding="utf-8")
    base_compose = DOCKER_COMPOSE_BASE.read_text(encoding="utf-8")
    prod_compose = DOCKER_COMPOSE_PROD.read_text(encoding="utf-8")

    assert "FROM python:3.12.12-slim-bookworm" in backend_dockerfile
    assert "FROM python:3.12.12-slim-bookworm" in sandbox_dockerfile
    assert "image: postgres:16.11-alpine3.23" in base_compose
    assert "image: caddy:2.10.2-alpine" in prod_compose


def test_backend_ci_runs_lint_and_type_checks() -> None:
    workflow_text = BACKEND_CI_WORKFLOW.read_text(encoding="utf-8")

    assert "      - name: Run backend lint" in workflow_text
    assert "python -m scripts.run_backend_lint" in workflow_text
    assert "python -m ruff check app/ tests/ --select F,E9,I" not in workflow_text
    assert "      - name: Run backend type checks" in workflow_text
    assert (
        "python -m mypy --strict --follow-imports=silent --ignore-missing-imports app/core/ app/api/ app/schemas/"
        in workflow_text
    )


def test_backend_ci_verifies_lockfile_without_mutating_branch() -> None:
    workflow_text = BACKEND_CI_WORKFLOW.read_text(encoding="utf-8")

    assert "    permissions:\n      contents: read" in workflow_text
    assert "      - name: Verify requirements.lock is up to date" in workflow_text
    assert "git push" not in workflow_text
    assert "git commit -m" not in workflow_text


def test_workflows_pin_third_party_actions_to_commit_shas() -> None:
    for workflow_path in (BACKEND_CI_WORKFLOW, OPS_REHEARSALS_WORKFLOW):
        workflow_text = workflow_path.read_text(encoding="utf-8")
        uses_refs = re.findall(r"uses:\s+([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)@([^\s#]+)", workflow_text)

        assert uses_refs, f"{workflow_path.name} should declare at least one third-party action."
        for action_name, ref in uses_refs:
            assert re.fullmatch(r"[0-9a-f]{40}", ref), (
                f"{workflow_path.name} leaves {action_name} pinned to {ref!r} instead of an immutable SHA."
            )


def test_backend_ci_runs_dependency_vulnerability_audit() -> None:
    workflow_text = BACKEND_CI_WORKFLOW.read_text(encoding="utf-8")

    assert "      - name: Audit locked dependencies for known vulnerabilities" in workflow_text
    assert "pip install pip-audit" in workflow_text
    assert "pip-audit -r requirements.lock" in workflow_text


def test_backend_ci_runs_strict_release_quality_gates() -> None:
    workflow_text = BACKEND_CI_WORKFLOW.read_text(encoding="utf-8")

    assert "python -m scripts.run_release_quality_gates --strict" in workflow_text


def test_bootstrap_prod_host_avoids_network_installers() -> None:
    script_text = (REPO_ROOT / "scripts" / "bootstrap-prod-host.sh").read_text(encoding="utf-8")

    assert "https://get.docker.com" not in script_text
    assert "apt-get install -y rclone" not in script_text


def test_dependabot_covers_backend_dependencies_and_workflows() -> None:
    config_text = DEPENDABOT_CONFIG.read_text(encoding="utf-8")

    assert 'package-ecosystem: "pip"' in config_text
    assert 'directory: "/backend"' in config_text
    assert 'package-ecosystem: "docker"' in config_text
    assert 'directory: "/docker"' in config_text
    assert 'package-ecosystem: "github-actions"' in config_text
    assert 'directory: "/"' in config_text


def test_deploy_workflow_does_not_print_full_merged_compose_on_validation_failure() -> None:
    workflow_text = BACKEND_CI_WORKFLOW.read_text(encoding="utf-8")

    assert "cat /tmp/merged-prod-compose.yml" not in workflow_text
    assert "grep -En 'published: \"(8000|5433)\"|^[[:space:]]+build:' /tmp/merged-prod-compose.yml >&2 || true" in workflow_text


def test_backup_db_script_requires_off_host_remote(tmp_path: Path):
    result, _, _ = _run_backup_db(tmp_path, set_rclone_remote=False)

    assert result.returncode == 1
    assert "RCLONE_REMOTE must be set for off-host backups" in result.stderr


def test_validate_host_env_script_accepts_private_ghcr_credentials(tmp_path: Path):
    result = _run_validate_host_env(
        tmp_path,
        "\n".join(
            [
                "DOMAIN=api.example.com",
                "PROMPTCODE_DB_PASSWORD=prod-db-password",
                "PROMPTCODE_JWT_SECRET=prod-jwt-secret-0123456789abcdef",
                "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=prod-sandbox-secret-0123456789-extra-bytes",
                "PROMPTCODE_EXECUTION_BROKER_URL=https://execution.example.com",
                "PROMPTCODE_GRADING_SIGNING_KEY=test-signing-key-32bytes-minimum-value",
                "PROMPTCODE_INTERVIEW_INTERNAL_TOKEN=test-internal-token-32bytes-minimum",
                "PROMPTCODE_OPENAI_API_KEY=sk-live-prod-key",
                "PROMPTCODE_METRICS_TOKEN=metrics-secret",
                "RCLONE_REMOTE=s3:promptcode/backups",
                "GHCR_USERNAME=promptcode-bot",
                "GHCR_TOKEN=ghp_example_token",
                "",
            ],
        ),
    )

    assert result.returncode == 0
    assert "Host environment OK" in result.stdout


def test_validate_host_env_script_accepts_public_ghcr_images_without_credentials(tmp_path: Path):
    result = _run_validate_host_env(
        tmp_path,
        "\n".join(
            [
                "DOMAIN=api.example.com",
                "PROMPTCODE_DB_PASSWORD=prod-db-password",
                "PROMPTCODE_JWT_SECRET=prod-jwt-secret-0123456789abcdef",
                "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=prod-sandbox-secret-0123456789-extra-bytes",
                "PROMPTCODE_EXECUTION_BROKER_URL=https://execution.example.com",
                "PROMPTCODE_GRADING_SIGNING_KEY=test-signing-key-32bytes-minimum-value",
                "PROMPTCODE_INTERVIEW_INTERNAL_TOKEN=test-internal-token-32bytes-minimum",
                "PROMPTCODE_OPENAI_API_KEY=sk-live-prod-key",
                "PROMPTCODE_METRICS_TOKEN=metrics-secret",
                "RCLONE_REMOTE=s3:promptcode/backups",
                "PROMPTCODE_GHCR_PUBLIC_IMAGES=true",
                "",
            ],
        ),
    )

    assert result.returncode == 0
    assert "public images" in result.stdout


def test_validate_host_env_script_rejects_missing_ghcr_setup_for_private_images(tmp_path: Path):
    result = _run_validate_host_env(
        tmp_path,
        "\n".join(
            [
                "DOMAIN=api.example.com",
                "PROMPTCODE_DB_PASSWORD=prod-db-password",
                "PROMPTCODE_JWT_SECRET=prod-jwt-secret-0123456789abcdef",
                "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=prod-sandbox-secret-0123456789-extra-bytes",
                "PROMPTCODE_EXECUTION_BROKER_URL=https://execution.example.com",
                "PROMPTCODE_GRADING_SIGNING_KEY=test-signing-key-32bytes-minimum-value",
                "PROMPTCODE_INTERVIEW_INTERNAL_TOKEN=test-internal-token-32bytes-minimum",
                "PROMPTCODE_OPENAI_API_KEY=sk-live-prod-key",
                "PROMPTCODE_METRICS_TOKEN=metrics-secret",
                "RCLONE_REMOTE=s3:promptcode/backups",
                "",
            ],
        ),
    )

    assert result.returncode == 1
    assert "GHCR_USERNAME must be set" in result.stderr
    assert "GHCR_TOKEN must be set" in result.stderr


def test_validate_prod_host_script_passes_with_required_dependencies(tmp_path: Path):
    deploy_dir = tmp_path / "deploy"
    result = _run_validate_prod_host(
        tmp_path,
        cron_entries=(
            f"0 3 * * * bash {deploy_dir}/scripts/backup-db.sh\n"
            f"*/5 * * * * bash {deploy_dir}/scripts/check-prod-health.sh\n"
            f"0 4 * * * bash {deploy_dir}/scripts/cleanup-interview.sh\n"
        ),
    )

    assert result.returncode == 0
    assert "Production host preflight OK" in result.stdout


@pytest.mark.parametrize(
    ("kwargs", "expected_message"),
    [
        ({"include_caddyfile": False}, "docker/Caddyfile.prod"),
        ({"include_seed_script": False}, "scripts/seed-prod-data.sh"),
        ({"include_cleanup_script": False}, "scripts/cleanup-interview.sh"),
    ],
)
def test_validate_prod_host_script_requires_deploy_assets(
    tmp_path: Path,
    kwargs: dict[str, bool],
    expected_message: str,
):
    deploy_dir = tmp_path / "deploy"
    result = _run_validate_prod_host(
        tmp_path,
        cron_entries=(
            f"0 3 * * * bash {deploy_dir}/scripts/backup-db.sh\n"
            f"*/5 * * * * bash {deploy_dir}/scripts/check-prod-health.sh\n"
            f"0 4 * * * bash {deploy_dir}/scripts/cleanup-interview.sh\n"
        ),
        **kwargs,
    )

    assert result.returncode == 1
    assert expected_message in result.stderr


def test_validate_prod_host_script_requires_rclone(tmp_path: Path):
    deploy_dir = tmp_path / "deploy"
    result = _run_validate_prod_host(
        tmp_path,
        include_rclone=False,
        cron_entries=(
            f"0 3 * * * bash {deploy_dir}/scripts/backup-db.sh\n"
            f"*/5 * * * * bash {deploy_dir}/scripts/check-prod-health.sh\n"
            f"0 4 * * * bash {deploy_dir}/scripts/cleanup-interview.sh\n"
        ),
    )

    assert result.returncode == 1
    assert "rclone must be installed" in result.stderr


def test_validate_prod_host_script_requires_backup_and_health_crons(tmp_path: Path):
    deploy_dir = tmp_path / "deploy"
    result = _run_validate_prod_host(
        tmp_path,
        cron_entries=f"0 3 * * * bash {deploy_dir}/scripts/backup-db.sh\n",
    )

    assert result.returncode == 1
    assert "Health-check cron is missing" in result.stderr


def test_validate_prod_host_requires_scheduled_source_cleanup(tmp_path: Path):
    deploy_dir = tmp_path / 'deploy'
    result = _run_validate_prod_host(tmp_path, cron_entries=(
        f'0 3 * * * bash {deploy_dir}/scripts/backup-db.sh\n'
        f'*/5 * * * * bash {deploy_dir}/scripts/check-prod-health.sh\n'))
    assert result.returncode != 0
    assert 'Interview cleanup cron is missing' in result.stderr


def test_cleanup_host_wrapper_dispatches_in_backend_container(tmp_path: Path):
    deploy_dir, _, fake_bin = _prepare_operational_script_fixture(tmp_path)
    capture = tmp_path / 'cleanup-command.txt'
    _write(fake_bin / 'docker', '#!/usr/bin/env bash\nset -euo pipefail\nprintf "%s\\n" "$@" > "${FAKE_CAPTURE}"\n')
    (fake_bin / 'docker').chmod(0o755)
    result = subprocess.run(['bash', str(REPO_ROOT / 'scripts' / 'cleanup-interview.sh')],
        capture_output=True, text=True, env={**os.environ, 'DEPLOY_DIR': str(deploy_dir),
            'PATH': f"{fake_bin}:{os.environ['PATH']}", 'FAKE_CAPTURE': str(capture)})
    assert result.returncode == 0
    args = capture.read_text().splitlines()
    assert args == ['compose', '-f', str(deploy_dir / 'docker-compose.yml'), '-f',
        str(deploy_dir / 'docker-compose.prod.yml'), 'exec', '-T', 'backend', 'python',
        '-m', 'scripts.cleanup_interview_sessions']
    workflow = BACKEND_CI_WORKFLOW.read_text()
    source_line = next(line for line in workflow.splitlines() if 'source: "docker-compose.yml,' in line)
    assert 'scripts/cleanup-interview.sh' in source_line


def test_validate_prod_host_script_rejects_crons_for_another_deploy_path(tmp_path: Path):
    result = _run_validate_prod_host(
        tmp_path,
        cron_entries=(
            "0 3 * * * bash /srv/promptcode/scripts/backup-db.sh\n"
            "*/5 * * * * bash /srv/promptcode/scripts/check-prod-health.sh\n"
        ),
    )

    assert result.returncode == 1
    assert "Backup cron is missing" in result.stderr


def test_setup_ghcr_login_script_logs_in_with_host_credentials(tmp_path: Path):
    result, capture_path = _run_setup_ghcr_login(
        tmp_path,
        "\n".join(
            [
                "GHCR_USERNAME=promptcode-bot",
                "GHCR_TOKEN=ghp_example_token",
                "",
            ],
        ),
    )

    assert result.returncode == 0
    assert "GHCR login refreshed" in result.stdout
    capture = capture_path.read_text(encoding="utf-8")
    assert "login ghcr.io -u promptcode-bot --password-stdin" in capture
    assert capture.endswith("ghp_example_token")


def test_setup_ghcr_login_script_skips_for_public_images(tmp_path: Path):
    result, capture_path = _run_setup_ghcr_login(
        tmp_path,
        "PROMPTCODE_GHCR_PUBLIC_IMAGES=true\n",
    )

    assert result.returncode == 0
    assert "Skipping GHCR login" in result.stdout
    assert not capture_path.exists()


def test_bootstrap_prod_host_fails_closed_when_no_firewall_is_active(tmp_path: Path):
    result, _ = _run_bootstrap_prod_host(
        tmp_path,
        ufw_active=False,
    )

    assert result.returncode == 1
    assert "ufw is not active" in result.stderr
    assert "PROMPTCODE_ALLOW_EXTERNAL_FIREWALL=1" in result.stderr


def test_bootstrap_prod_host_allows_explicit_external_firewall_management(tmp_path: Path):
    result, deploy_dir = _run_bootstrap_prod_host(
        tmp_path,
        ufw_active=False,
        allow_external_firewall=True,
    )

    assert result.returncode == 0
    assert "relying on an external firewall" in result.stdout
    assert (deploy_dir / "scripts" / "validate-host-env.sh").exists()
    assert (deploy_dir / "scripts" / "setup-ghcr-login.sh").exists()
    assert (deploy_dir / "scripts" / "validate-prod-host.sh").exists()
    assert (deploy_dir / 'scripts' / 'cleanup-interview.sh').exists()
    cron = (tmp_path / 'crontab.txt').read_text()
    assert f"0 4 * * * DEPLOY_DIR='{deploy_dir}' bash '{deploy_dir}/scripts/cleanup-interview.sh'" in cron


def test_bootstrap_prod_host_requires_preinstalled_rclone(tmp_path: Path):
    result, _ = _run_bootstrap_prod_host(
        tmp_path,
        ufw_active=True,
        include_rclone=False,
    )

    assert result.returncode == 1
    assert "rclone must be installed from a trusted package source" in result.stderr


def test_backup_db_script_creates_local_backup_and_uploads_off_host(tmp_path: Path):
    result, backups_dir, remote_dir = _run_backup_db(tmp_path)

    assert result.returncode == 0
    backup_files = list(backups_dir.glob("promptcode-*.sql.gz"))
    assert len(backup_files) == 1
    with gzip.open(backup_files[0], "rt", encoding="utf-8") as handle:
        assert "CREATE TABLE backup_check" in handle.read()
    uploaded_files = list(remote_dir.glob("promptcode-*"))
    assert {path.name for path in uploaded_files} == {backup_files[0].name,
        backup_files[0].name.replace('.sql.gz', '.artifacts.tar.gz'),
        backup_files[0].name.replace('.sql.gz', '.sha256')}
    assert (backups_dir / "last-successful-backup.txt").exists()
    assert (backups_dir / ".last-success-timestamp").exists()


def test_partial_backup_upload_does_not_advance_success_marker(tmp_path: Path):
    result, backups_dir, _ = _run_backup_db(tmp_path)
    assert result.returncode == 0
    marker = backups_dir / '.last-success-timestamp'
    marker.write_text('123\n')
    _write(tmp_path / 'bin' / 'rclone', """#!/usr/bin/env bash
set -euo pipefail
if [[ "$2" == *.sha256 ]]; then exit 1; fi
mkdir -p "$3"
cp "$2" "$3/"
""")
    result = subprocess.run(['bash', str(BACKUP_DB_SCRIPT)], capture_output=True, text=True,
        env={**os.environ, 'DEPLOY_DIR': str(tmp_path / 'deploy'),
             'PATH': f"{tmp_path / 'bin'}:{os.environ['PATH']}"})
    assert result.returncode != 0
    assert marker.read_text() == '123\n'
    assert not list(backups_dir.glob('.backup.*'))


def test_corrupt_source_backup_is_rejected_before_database_restore(tmp_path: Path):
    result, backups_dir, _ = _run_backup_db(tmp_path)
    assert result.returncode == 0
    backup = next(backups_dir.glob('promptcode-*.sql.gz'))
    archive = backups_dir / backup.name.replace('.sql.gz', '.artifacts.tar.gz')
    archive.write_bytes(b'corrupt frozen source')
    import shutil
    shutil.rmtree(tmp_path / 'deploy' / 'artifacts')
    capture = tmp_path / 'restored.sql'
    _write(tmp_path / 'bin' / 'docker', f"#!/usr/bin/env bash\ncat > {str(capture)!r}\n")
    result = subprocess.run(['bash', str(RESTORE_DB_SCRIPT), str(backup)], capture_output=True, text=True,
        env={**os.environ, 'DEPLOY_DIR': str(tmp_path / 'deploy'),
             'PATH': f"{tmp_path / 'bin'}:{os.environ['PATH']}"})
    assert result.returncode != 0 and 'checksum mismatch' in result.stderr
    assert not capture.exists()


def test_backup_restore_preserves_active_source_and_excludes_dependencies(tmp_path: Path):
    import shutil
    import tarfile
    result, backups_dir, _ = _run_backup_db(tmp_path)
    assert result.returncode == 0
    root = tmp_path / 'deploy' / 'artifacts'
    sid = '11111111-1111-1111-1111-111111111111'
    (root / sid / 'node_modules').mkdir(parents=True)
    (root / sid / 'main.py').write_text('active coding progress')
    (root / sid / 'node_modules' / 'generated.js').write_text('rebuildable dependency')
    (root / f'{sid}.starter').mkdir()
    env = {**os.environ, 'DEPLOY_DIR': str(tmp_path / 'deploy'),
           'PATH': f"{tmp_path / 'bin'}:{os.environ['PATH']}"}
    result = subprocess.run(['bash', str(BACKUP_DB_SCRIPT)], capture_output=True, text=True, env=env)
    assert result.returncode == 0
    backup = max(backups_dir.glob('promptcode-*.sql.gz'), key=lambda path: path.stat().st_mtime_ns)
    archive = backups_dir / backup.name.replace('.sql.gz', '.artifacts.tar.gz')
    with tarfile.open(archive) as source:
        assert f'{sid}/main.py' in source.getnames()
        assert not any('node_modules' in name for name in source.getnames())
    shutil.rmtree(root)
    capture = tmp_path / 'restored.sql'
    _write(tmp_path / 'bin' / 'docker', f"#!/usr/bin/env bash\ncat > {str(capture)!r}\n")
    result = subprocess.run(['bash', str(RESTORE_DB_SCRIPT), str(backup)], capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr
    assert (root / sid / 'main.py').read_text() == 'active coding progress'
    assert (root / f'{sid}.starter').is_dir()
    assert capture.exists()


def test_restore_rejects_existing_artifact_tree_before_database_write(tmp_path: Path):
    result, backups_dir, _ = _run_backup_db(tmp_path)
    assert result.returncode == 0
    backup = next(backups_dir.glob('promptcode-*.sql.gz'))
    capture = tmp_path / 'restored.sql'
    _write(tmp_path / 'bin' / 'docker', f"#!/usr/bin/env bash\ncat > {str(capture)!r}\n")
    result = subprocess.run(['bash', str(RESTORE_DB_SCRIPT), str(backup)], capture_output=True, text=True,
        env={**os.environ, 'DEPLOY_DIR': str(tmp_path / 'deploy'),
             'PATH': f"{tmp_path / 'bin'}:{os.environ['PATH']}"})
    assert result.returncode != 0 and 'empty artifact destination' in result.stderr
    assert not capture.exists()


@pytest.mark.parametrize('problem', [{'grading_failed': '1'}, {'grading_stale': '1'}, {'grading_queue_age': '301'}])
def test_health_check_alerts_on_durable_grading_problems(tmp_path: Path, problem):
    result, _ = _run_check_prod_health(tmp_path, **problem)
    assert result.returncode != 0
    assert 'Grading backlog, failed job, or expired lease' in result.stderr


def test_restore_db_script_requires_remote_for_missing_local_backup(tmp_path: Path):
    result, _, _, _ = _run_restore_db(
        tmp_path,
        "promptcode-missing.sql.gz",
        set_rclone_remote=False,
    )

    assert result.returncode == 1
    assert "RCLONE_REMOTE must be set to download non-local backups" in result.stderr


def test_restore_db_script_downloads_remote_backup_and_restores_it(tmp_path: Path):
    remote_backup = tmp_path / "remote" / "promptcode-remote.sql.gz"
    remote_backup.parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(remote_backup, "wt", encoding="utf-8") as handle:
        handle.write("INSERT INTO restore_check VALUES (1);\n")

    result, restore_capture, backups_dir, _ = _run_restore_db(
        tmp_path,
        remote_backup.name,
    )

    assert result.returncode == 0
    assert restore_capture.read_text(encoding="utf-8") == "INSERT INTO restore_check VALUES (1);\n"
    assert (backups_dir / remote_backup.name).exists()


def test_ops_rehearsal_workflow_proves_schema_boundary_after_rollback() -> None:
    workflow_text = OPS_REHEARSALS_WORKFLOW.read_text(encoding="utf-8")

    assert "      - name: Auto rollback after failed deploy" in workflow_text
    assert 'IMAGE_TAG="${PREV_TAG}" docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build' in workflow_text
    assert "rollback_boundary_probe" in workflow_text
    assert "schema_probe_still_applied" in workflow_text
    assert "healthy_after_rollback" in workflow_text
    assert "alembic downgrade -1" in workflow_text


def test_check_prod_health_script_passes_with_healthy_signals(tmp_path: Path):
    result, _ = _run_check_prod_health(tmp_path)

    assert result.returncode == 0
    assert "Production health check passed" in result.stdout


def test_check_prod_health_script_uses_run_scoped_metrics_tempfile(tmp_path: Path):
    result, metrics_status_file = _run_check_prod_health(tmp_path, capture_mktemp=True)

    assert result.returncode == 0
    assert not metrics_status_file.exists()


@pytest.mark.parametrize(
    ("kwargs", "expected_message"),
    [
        ({"metrics_status": "500"}, "Metrics scrape failed"),
        ({"heartbeat_age": "61"}, "Worker heartbeat age exceeded 60s"),
        ({"queue_depth": "51"}, "Queue depth 51 exceeded 50"),
        ({"backup_age_seconds": 93601}, "Last successful backup is older than 93600s"),
        ({"last_deploy_status": "deploying 123 abcdef"}, "Last deploy status is not healthy"),
    ],
)
def test_check_prod_health_script_fails_for_unhealthy_signals(
    tmp_path: Path,
    kwargs: dict[str, str | int],
    expected_message: str,
):
    result, _ = _run_check_prod_health(tmp_path, **kwargs)

    assert result.returncode == 1
    assert expected_message in result.stderr


@pytest.mark.parametrize('key,valid', [('sk-deepseek-test-key', True), ('', False), ('sk-placeholder-key', False)])
def test_validate_host_env_requires_deepseek_key_for_deepseek_endpoint(tmp_path, key, valid):
    result = _run_validate_host_env(tmp_path, '\n'.join([
        'DOMAIN=api.example.com',
        'PROMPTCODE_DB_PASSWORD=prod-db-password',
        'PROMPTCODE_JWT_SECRET=prod-jwt-secret-0123456789abcdef',
        'PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=prod-sandbox-secret-0123456789-extra-bytes',
        'PROMPTCODE_EXECUTION_BROKER_URL=https://execution.example.com',
        'PROMPTCODE_GRADING_SIGNING_KEY=test-signing-key-32bytes-minimum-value',
        'PROMPTCODE_INTERVIEW_INTERNAL_TOKEN=test-internal-token-32bytes-minimum',
        'PROMPTCODE_OPENAI_API_KEY=old-provider-key',
        'PROMPTCODE_OPENAI_BASE_URL=https://api.deepseek.com',
        f'DEEPSEEK_API_KEY={key}',
        'PROMPTCODE_METRICS_TOKEN=metrics-secret',
        'RCLONE_REMOTE=s3:promptcode/backups',
        'PROMPTCODE_GHCR_PUBLIC_IMAGES=true',
        '',
    ]))
    assert (result.returncode == 0) is valid
    if not valid:
        assert 'DEEPSEEK_API_KEY' in result.stderr


@pytest.mark.parametrize("broker_url", ["", "http://execution.example.com", "https://127.0.0.1",
                                      "https://user:password@execution.example.com"])
def test_host_preflight_refuses_unsafe_execution_management(tmp_path, broker_url):
    env = "\n".join([
        "DOMAIN=app.example.com", "PROMPTCODE_DB_PASSWORD=test-db-password",
        "PROMPTCODE_JWT_SECRET=test-jwt-key-of-at-least-32bytes-length",
        "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=test-management-key-of-at-least-32bytes",
        "PROMPTCODE_GRADING_SIGNING_KEY=test-grading-key-of-at-least-32bytes",
        "PROMPTCODE_INTERVIEW_INTERNAL_TOKEN=test-internal-key-of-at-least-32bytes",
        "PROMPTCODE_EXECUTION_BROKER_URL=" + broker_url,
        "PROMPTCODE_OPENAI_API_KEY=test-provider-key", "PROMPTCODE_METRICS_TOKEN=test-metrics-key",
        "RCLONE_REMOTE=test:backup", "PROMPTCODE_GHCR_PUBLIC_IMAGES=true"])
    result = _run_validate_host_env(tmp_path, env)
    assert result.returncode == 1
    assert "PROMPTCODE_EXECUTION_BROKER_URL" in result.stderr


def test_host_preflight_validates_host_side_of_private_ca_mount(tmp_path):
    import ssl
    ca = ssl.get_default_verify_paths().cafile
    if not ca or not Path(ca).is_file():
        pytest.skip("System CA bundle unavailable")
    deploy = tmp_path / "deploy"
    ca_dir = deploy / "docker" / "broker-ca"
    ca_dir.mkdir(parents=True)
    (ca_dir / "ca.crt").write_bytes(Path(ca).read_bytes())
    env = "\n".join([
        "DOMAIN=app.example.com", "PROMPTCODE_DB_PASSWORD=test-db-password",
        "PROMPTCODE_JWT_SECRET=test-jwt-key-of-at-least-32bytes-length",
        "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=test-management-key-of-at-least-32bytes",
        "PROMPTCODE_GRADING_SIGNING_KEY=test-grading-key-of-at-least-32bytes",
        "PROMPTCODE_INTERVIEW_INTERNAL_TOKEN=test-internal-key-of-at-least-32bytes",
        "PROMPTCODE_EXECUTION_BROKER_URL=https://execution.example.com",
        "PROMPTCODE_EXECUTION_BROKER_CA_FILE=/etc/promptcode/broker-ca/ca.crt",
        "PROMPTCODE_OPENAI_API_KEY=test-provider-key", "PROMPTCODE_METRICS_TOKEN=test-metrics-key",
        "RCLONE_REMOTE=test:backup", "PROMPTCODE_GHCR_PUBLIC_IMAGES=true"])
    result = _run_validate_host_env(tmp_path, env)
    assert result.returncode == 0, result.stderr


# --- Managed deployment (Vercel frontend + Modal backend + Supabase) --------------
# Assertions only; the existing deployment-contract tests above are untouched.

MODAL_APP = REPO_ROOT / "backend" / "modal_app.py"
VERCEL_CONFIG = REPO_ROOT / "vercel.json"
ENV_EXAMPLE = REPO_ROOT / ".env.example"
REQUIREMENTS_TXT = REPO_ROOT / "backend" / "requirements.txt"
MANAGED_DEPLOYMENT_DOC = REPO_ROOT / "docs" / "managed-deployment.md"
FRONTEND_DIR = REPO_ROOT / "frontend"

# Pretty URLs the FastAPI app serves from frontend/*.html (see app/main.py). The
# static host must reproduce them, or deep links land on the SPA fallback instead.
_EXPECTED_VERCEL_ROUTES = {
    "/api/:path*": None,  # proxied to Modal, asserted separately
    "/static/:path*": "/frontend/:path*",
    "/challenges": "/frontend/interview-challenges.html",
    "/challenges/:slug": "/frontend/interview-challenge.html",
    "/session/:id/report": "/frontend/interview-report.html",
    "/session/:id": "/frontend/interview-session.html",
    "/dashboard": "/frontend/interview-dashboard.html",
    "/onboarding": "/frontend/interview-onboarding.html",
    "/privacy": "/frontend/interview-privacy.html",
    "/settings": "/frontend/interview-settings.html",
    "/progress": "/frontend/interview-progress.html",
    "/grading": "/frontend/interview-grading.html",
}

_MANAGED_SETTINGS = [
    "PROMPTCODE_EXECUTION_BACKEND",
    "PROMPTCODE_MODAL_APP_NAME",
    "PROMPTCODE_MODAL_ENVIRONMENT",
    "PROMPTCODE_MODAL_SANDBOX_IMAGE_NODE",
    "PROMPTCODE_MODAL_SANDBOX_IMAGE_PYTHON",
    "PROMPTCODE_MODAL_SANDBOX_TIMEOUT_SECONDS",
    "PROMPTCODE_MODAL_SANDBOX_CPU",
    "PROMPTCODE_MODAL_SANDBOX_MEMORY_MB",
    "PROMPTCODE_MODAL_SANDBOX_OUTPUT_LIMIT_BYTES",
    "PROMPTCODE_MODAL_SANDBOX_PIDS_LIMIT",
    "PROMPTCODE_MODAL_FUNCTION_TIMEOUT_SECONDS",
    "PROMPTCODE_STORAGE_BACKEND",
    "PROMPTCODE_SUPABASE_URL",
    "PROMPTCODE_SUPABASE_SERVICE_ROLE_KEY",
    "PROMPTCODE_SUPABASE_STORAGE_BUCKET",
    "PROMPTCODE_SUPABASE_STORAGE_TIMEOUT_SECONDS",
    "PROMPTCODE_SUPABASE_MAX_OBJECT_BYTES",
    "PROMPTCODE_SUPABASE_KEEPALIVE_ENABLED",
    "PROMPTCODE_SUPABASE_KEEPALIVE_INTERVAL_SECONDS",
]

_SECRET_MARKERS = ("service_role", "service-role", "sk-live", "sk-proj", "eyJhbGciOi", "postgresql+asyncpg://")


def _load_vercel_config() -> dict:
    import json

    return json.loads(VERCEL_CONFIG.read_text(encoding="utf-8"))


def _load_modal_app_with_stub(monkeypatch):
    """Import backend/modal_app.py against a stubbed ``modal`` SDK."""
    import importlib.util
    import sys
    import types

    calls: dict = {"functions": [], "asgi": None, "requirements": [], "dirs": [],
                   "dir_ignores": []}

    class _FakeImage:
        def pip_install_from_requirements(self, path):
            calls["requirements"].append(str(path))
            return self

        def add_local_dir(self, local, remote_path=None, ignore=None, **_kwargs):
            calls["dirs"].append((str(local), remote_path))
            calls["dir_ignores"].append((remote_path, str(local), list(ignore or [])))
            return self

        def env(self, _env):
            return self

    def _fake_function(**kwargs):
        def wrap(fn):
            calls["functions"].append((fn.__name__, kwargs))
            return fn

        return wrap

    class _FakeApp:
        def __init__(self, name):
            self.name = name

        def function(self, **kwargs):
            return _fake_function(**kwargs)

    fake = types.ModuleType("modal")
    fake.App = _FakeApp
    fake.Image = types.SimpleNamespace(debian_slim=lambda **_kwargs: _FakeImage())
    fake.Secret = types.SimpleNamespace(from_name=lambda name, **_kwargs: ("modal-secret", name))
    fake.function = _fake_function
    fake.Period = lambda **kwargs: ("period", kwargs)
    fake.Cron = lambda expression, **kwargs: ("cron", expression)

    def _fake_asgi_app(**_kwargs):
        def wrap(fn):
            calls["asgi"] = fn.__name__
            return fn

        return wrap

    fake.asgi_app = _fake_asgi_app

    monkeypatch.setitem(sys.modules, "modal", fake)
    spec = importlib.util.spec_from_file_location("modal_app_under_test", MODAL_APP)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, calls


def test_modal_app_parses_as_python():
    import ast

    ast.parse(MODAL_APP.read_text(encoding="utf-8"))


def test_modal_app_serves_the_existing_fastapi_app(monkeypatch):
    module, calls = _load_modal_app_with_stub(monkeypatch)

    assert module.app.name == "promptcode"
    assert calls["asgi"] == "fastapi_app"
    registered = dict(calls["functions"])
    assert "fastapi_app" in registered
    # The FastAPI app must be served, not re-implemented: the ASGI function imports
    # app.main at container start.
    assert "from app.main import app as application" in MODAL_APP.read_text(encoding="utf-8")


def test_modal_app_ships_app_source_and_runtime_data(monkeypatch):
    """The image must carry the runtime data the app resolves from the repo root.

    ``app/services/interview/registry.py`` reads ``parents[4]/challenges`` (registry
    plus every starter tree) and ``app/services/evaluation/weight_profile.py`` reads
    ``backend/benchmarks``. Shipping only ``app/`` would deploy an image in which no
    challenge can be started, so these are asserted as required image inputs.
    """
    _module, calls = _load_modal_app_with_stub(monkeypatch)

    assert calls["requirements"] == [str(REQUIREMENTS_TXT)]
    shipped = {remote: Path(local).name for local, remote in calls["dirs"]}
    assert shipped == {
        "/root/backend/app": "app",
        "/root/challenges": "challenges",
        "/root/backend/benchmarks": "benchmarks",
    }

    # node_modules accounts for ~608 MB of the 613 MB challenge tree, is skipped by
    # the workspace starter copy, and belongs in the candidate sandbox image instead.
    ignore = {remote: rules for remote, _local, rules in calls["dir_ignores"]}
    assert any("node_modules" in rule for rule in ignore["/root/challenges"])


def test_modal_app_runs_grading_as_a_spawnable_background_function(monkeypatch):
    _module, calls = _load_modal_app_with_stub(monkeypatch)

    registered = dict(calls["functions"])
    grading = registered["grade_pending_jobs"]
    assert grading["schedule"] == ("period", {"seconds": 60})
    assert grading["max_containers"] == 2
    # A background function, never a web endpoint: the 150 s HTTP cap cannot apply.
    source = MODAL_APP.read_text(encoding="utf-8")
    assert "process_one_grading_job" in source
    assert "validate_production_startup" in source
    # The ASGI function must not drain the queue: grading is never done inside a
    # request, where Modal's 150 s cap and the CORS-incompatible 303 fallback apply.
    asgi_body = source.split("def fastapi_app", 1)[1].split("@app.function", 1)[0]
    assert "process_one_grading_job" not in asgi_body, asgi_body
    # NOTE: no `.spawn()` call exists in this app. Grading latency is bounded by the
    # schedule above (PROMPTCODE_MODAL_GRADING_POLL_SECONDS); an eager spawn from the
    # API after enqueueing is a documented *option*, not wired code, so asserting
    # ".spawn()" in source would only ever match the docstring.


def test_modal_app_schedules_the_supabase_keepalive_with_a_cron(monkeypatch):
    _module, calls = _load_modal_app_with_stub(monkeypatch)

    registered = dict(calls["functions"])
    assert registered["supabase_keepalive"]["schedule"] == ("cron", "0 */6 * * *")
    source = MODAL_APP.read_text(encoding="utf-8")
    assert "supabase_keepalive_enabled" in source
    assert "SELECT 1" in source


def test_modal_app_takes_runtime_secrets_from_a_modal_secret(monkeypatch):
    module, _calls = _load_modal_app_with_stub(monkeypatch)

    assert module.env_secret == ("modal-secret", "promptcode-env")
    source = MODAL_APP.read_text(encoding="utf-8")
    for marker in _SECRET_MARKERS + ("SUPABASE_SERVICE_ROLE_KEY=",):
        assert marker not in source


def test_vercel_config_hosts_static_frontend_without_a_build_step():
    config = _load_vercel_config()

    assert config["cleanUrls"] is False
    assert config["trailingSlash"] is False
    assert "buildCommand" not in config
    assert "framework" not in config or config["framework"] is None
    assert "rewrites" in config


def test_vercel_config_preserves_every_pretty_route():
    config = _load_vercel_config()
    rewrites = {rule["source"]: rule["destination"] for rule in config["rewrites"]}

    for source, destination in _EXPECTED_VERCEL_ROUTES.items():
        assert source in rewrites, f"{source} is not routed by vercel.json"
        if destination is not None:
            assert rewrites[source] == destination

    # Every rewrite target that is not a path pattern must be a real file. Vercel
    # serves the repository root, so each target is prefixed with ``/frontend/``.
    for source, destination in rewrites.items():
        if not destination.startswith("/") or ":" in destination:
            continue
        assert destination.startswith("/frontend/"), (
            f"{source} must target the deployed frontend/ tree, got {destination}"
        )
        assert (REPO_ROOT / destination.lstrip("/")).is_file(), (
            f"{source} rewrites to missing file {destination}"
        )

    # The SPA fallback must be last so it cannot shadow a real route, and must not
    # swallow API, static or frontend traffic.
    catch_all = config["rewrites"][-1]
    assert catch_all["destination"] == "/frontend/index.html"
    assert "api" in catch_all["source"] and "static" in catch_all["source"]
    assert "frontend/" in catch_all["source"]

    # Routes the FastAPI app answers with a 307 to the matching .html file.
    redirects = {rule["source"]: rule["destination"] for rule in config["redirects"]}
    assert redirects == {
        "/login": "/frontend/login.html",
        "/signup": "/frontend/signup.html",
        "/practice": "/dashboard",
    }


def test_vercel_deployment_excludes_everything_but_the_frontend():
    """The Vercel project deploys the repository root, so the rest must be excluded.

    Without `.vercelignore`, an existing static file wins over the SPA catch-all
    rewrite and the whole repository is published — including the challenge answer
    keys in ``challenges/<slug>/SOLUTION.md`` (deliberately blocked from the API by
    ``app/services/interview/registry.py``), the backend source and docs.

    ``/*`` is anchored to the repository root and does not match nested paths, so the
    negations re-include the frontend and the config while nested files stay included.
    """
    ignore = REPO_ROOT / ".vercelignore"
    assert ignore.is_file(), "a root .vercelignore is required to limit the deployment"

    patterns = [
        line.strip()
        for line in ignore.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    assert patterns == ["/*", "!/frontend", "!/vercel.json"], patterns

    # The answer keys must exist for this guard to be meaningful.
    solution_keys = sorted((REPO_ROOT / "challenges").glob("*/SOLUTION.md"))
    assert solution_keys, "expected challenge SOLUTION.md files to be present"


def test_vercel_config_proxies_api_to_the_modal_backend():
    config = _load_vercel_config()
    api_rewrite = next(rule for rule in config["rewrites"] if rule["source"] == "/api/:path*")

    destination = api_rewrite["destination"]
    assert destination.startswith("https://")
    assert destination.endswith(".modal.run/api/:path*")
    assert "localhost" not in destination and "127.0.0.1" not in destination


def test_vercel_config_sets_security_headers():
    config = _load_vercel_config()
    headers = {
        header["key"]: header["value"]
        for rule in config["headers"]
        for header in rule["headers"]
    }

    assert headers["Strict-Transport-Security"].startswith("max-age=31536000")
    assert "includeSubDomains" in headers["Strict-Transport-Security"]
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["Referrer-Policy"] == "strict-origin-when-cross-origin"
    csp = headers["Content-Security-Policy"]
    assert "default-src 'self'" in csp
    assert "object-src 'none'" in csp
    assert "frame-ancestors 'none'" in csp
    assert "connect-src 'self'" in csp
    assert "script-src 'self'" in csp
    # The static HTML has no inline scripts, so the static host must not need
    # 'unsafe-inline' (app/main.py enforces the same rule at runtime).
    assert "'unsafe-inline'" not in csp.split("script-src")[1].split(";")[0]


def test_vercel_config_contains_no_provider_or_database_secrets():
    config_text = VERCEL_CONFIG.read_text(encoding="utf-8")

    assert "SUPABASE_SERVICE_ROLE_KEY" not in config_text
    assert "MODAL_TOKEN" not in config_text
    assert "DEEPSEEK_API_KEY" not in config_text
    assert "postgresql" not in config_text


def test_frontend_never_carries_a_provider_or_database_secret():
    forbidden = ("SUPABASE_SERVICE_ROLE_KEY", "MODAL_TOKEN_SECRET", "DEEPSEEK_API_KEY", "GRADING_SIGNING_KEY")
    for path in [*FRONTEND_DIR.glob("*.html"), *FRONTEND_DIR.glob("*.js"), *FRONTEND_DIR.glob("js/**/*.js")]:
        source = path.read_text(encoding="utf-8")
        for marker in forbidden:
            assert marker not in source, f"{path.name} references {marker}"


def test_requirements_pin_modal_and_keep_docker_for_the_docker_backend():
    requirements = REQUIREMENTS_TXT.read_text(encoding="utf-8")

    pinned = [line for line in requirements.splitlines() if line.strip().startswith("modal==")]
    assert len(pinned) == 1, "modal must be added exactly once, pinned to an exact version"
    assert "docker==7.1.0" in requirements, "the docker backend still needs the docker SDK"
    for existing in ("fastapi==0.142.2", "asyncpg==0.31.0", "alembic==1.18.4", "uvicorn[standard]==0.34.0"):
        assert existing in requirements, f"{existing} pin was removed"


def test_env_example_documents_every_managed_deployment_setting():
    env_example = ENV_EXAMPLE.read_text(encoding="utf-8")
    config_source = (REPO_ROOT / "backend" / "app" / "core" / "config.py").read_text(encoding="utf-8")

    for name in _MANAGED_SETTINGS:
        assert f"\n{name}=" in env_example, f"{name} is missing from .env.example"
        field = name.removeprefix("PROMPTCODE_").lower()
        assert f"{field}:" in config_source, f"{name} is not a Settings field"

    # The three provider facts an operator must not miss.
    assert "spend limit" in env_example.lower()
    assert "prepared statement" in env_example.lower()
    assert "hobby" in env_example.lower()


def test_managed_deployment_doc_covers_required_operator_steps():
    doc = MANAGED_DEPLOYMENT_DOC.read_text(encoding="utf-8")

    for required in (
        "$0",
        "alembic upgrade head",
        "alembic downgrade",
        "150",
        "prepared statement",
        "vercel.json",
        "modal deploy",
        "spend limit",
        "non-commercial",
        "not verified",
        "https://modal.com/docs/guide/webhook-timeouts",
        "https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL",
        "https://vercel.com/docs/plans/hobby",
    ):
        assert required in doc, f"managed-deployment.md must mention {required!r}"
