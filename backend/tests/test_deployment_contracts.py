from __future__ import annotations

import gzip
import os
import subprocess
import time
import uuid
from pathlib import Path

import pytest
from sqlalchemy import Column, Index, MetaData, String, Table, UniqueConstraint, types
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect

from app.db.alembic_compare import compare_type, should_include_object
from app.db.types import GUID
from app.db.types import JSONType
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
    deploy_dir.mkdir(parents=True)
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
                "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=prod-sandbox-secret-0123456789",
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
        "validate-host-env.sh",
        "setup-ghcr-login.sh",
    ):
        if script_path == "seed-prod-data.sh" and not include_seed_script:
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
    _write(
        fake_bin / "apt-get",
        """#!/usr/bin/env bash
set -euo pipefail
if [[ "$1" == "update" ]]; then
  exit 0
elif [[ "$1" == "install" && "$2" == "-y" && "$3" == "rclone" ]]; then
  cat > "${FAKE_BIN_DIR}/rclone" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
exit 0
EOF
  chmod +x "${FAKE_BIN_DIR}/rclone"
  exit 0
else
  echo "unexpected apt-get invocation: $*" >&2
  exit 1
fi
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
                "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=prod-sandbox-secret-0123456789",
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
                "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=prod-sandbox-secret-0123456789",
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
                "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=prod-sandbox-secret-0123456789",
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
        ),
    )

    assert result.returncode == 0
    assert "Production host preflight OK" in result.stdout


@pytest.mark.parametrize(
    ("kwargs", "expected_message"),
    [
        ({"include_caddyfile": False}, "docker/Caddyfile.prod"),
        ({"include_seed_script": False}, "scripts/seed-prod-data.sh"),
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


def test_backup_db_script_creates_local_backup_and_uploads_off_host(tmp_path: Path):
    result, backups_dir, remote_dir = _run_backup_db(tmp_path)

    assert result.returncode == 0
    backup_files = list(backups_dir.glob("promptcode-*.sql.gz"))
    assert len(backup_files) == 1
    with gzip.open(backup_files[0], "rt", encoding="utf-8") as handle:
        assert "CREATE TABLE backup_check" in handle.read()
    uploaded_files = list(remote_dir.glob("promptcode-*.sql.gz"))
    assert [path.name for path in uploaded_files] == [backup_files[0].name]
    assert (backups_dir / "last-successful-backup.txt").exists()
    assert (backups_dir / ".last-success-timestamp").exists()


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
