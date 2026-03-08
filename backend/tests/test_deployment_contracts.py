from __future__ import annotations

import gzip
import os
import subprocess
import time
from pathlib import Path

import pytest

from app.db.types import JSONType
from app.models.challenge import Challenge


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATE_ENV_SCRIPT = REPO_ROOT / "scripts" / "validate-env.sh"
CHECK_PROD_HEALTH_SCRIPT = REPO_ROOT / "scripts" / "check-prod-health.sh"
BACKUP_DB_SCRIPT = REPO_ROOT / "scripts" / "backup-db.sh"
RESTORE_DB_SCRIPT = REPO_ROOT / "scripts" / "restore-db.sh"
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


def _run_check_prod_health(
    tmp_path: Path,
    *,
    metrics_status: str = "200",
    heartbeat_age: str = "5",
    queue_depth: str = "0",
    backup_age_seconds: int = 300,
    last_deploy_status: str = "success 123 abcdef",
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

    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:{env['PATH']}"
    env["DEPLOY_DIR"] = str(deploy_dir)
    env["FAKE_METRICS_STATUS"] = metrics_status
    env["FAKE_HEARTBEAT_AGE"] = heartbeat_age
    env["FAKE_QUEUE_DEPTH"] = queue_depth

    return subprocess.run(
        ["bash", str(CHECK_PROD_HEALTH_SCRIPT)],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


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


def test_challenge_tags_column_uses_json_contract():
    assert isinstance(Challenge.__table__.c.tags.type, JSONType)


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
    assert (
        'IMAGE_TAG="$ROLLBACK_TAG" docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build'
        in workflow_text
    )
    assert 'echo "$ROLLBACK_TAG" > /opt/promptcode/.current-image-tag' in workflow_text
    assert "rolled_back %s %s" in workflow_text


def test_backup_db_script_requires_off_host_remote(tmp_path: Path):
    result, _, _ = _run_backup_db(tmp_path, set_rclone_remote=False)

    assert result.returncode == 1
    assert "RCLONE_REMOTE must be set for off-host backups" in result.stderr


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
    result = _run_check_prod_health(tmp_path)

    assert result.returncode == 0
    assert "Production health check passed" in result.stdout


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
    result = _run_check_prod_health(tmp_path, **kwargs)

    assert result.returncode == 1
    assert expected_message in result.stderr
