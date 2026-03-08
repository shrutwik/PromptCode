#!/usr/bin/env bash
# restore-db.sh — Restore a PromptCode PostgreSQL backup locally or from rclone.

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"
BACKUP_DIR="${BACKUP_DIR:-${DEPLOY_DIR}/backups}"
BACKUP_REF="${1:-}"

if [[ -z "${BACKUP_REF}" ]]; then
    echo "Usage: bash ${0##*/} <backup-file.sql.gz>" >&2
    exit 1
fi

if [[ -f "${DEPLOY_DIR}/.env" ]]; then
    # shellcheck disable=SC1090
    set -a; source "${DEPLOY_DIR}/.env"; set +a
fi

PROMPTCODE_DB_USER="${PROMPTCODE_DB_USER:-promptcode}"
PROMPTCODE_DB_NAME="${PROMPTCODE_DB_NAME:-promptcode}"

LOCAL_BACKUP="${BACKUP_REF}"
if [[ ! -f "${LOCAL_BACKUP}" ]]; then
    if [[ -z "${RCLONE_REMOTE:-}" ]]; then
        echo "[restore] RCLONE_REMOTE must be set to download non-local backups." >&2
        exit 1
    fi
    if ! command -v rclone >/dev/null 2>&1; then
        echo "[restore] rclone is required to download remote backups." >&2
        exit 1
    fi
    mkdir -p "${BACKUP_DIR}"
    LOCAL_BACKUP="${BACKUP_DIR}/$(basename "${BACKUP_REF}")"
    echo "[restore] Downloading $(basename "${BACKUP_REF}") from ${RCLONE_REMOTE}..."
    rclone copyto "${RCLONE_REMOTE%/}/$(basename "${BACKUP_REF}")" "${LOCAL_BACKUP}"
fi

if [[ ! -f "${LOCAL_BACKUP}" ]]; then
    echo "[restore] Backup file not found: ${LOCAL_BACKUP}" >&2
    exit 1
fi

echo "[restore] Restoring ${LOCAL_BACKUP} into ${PROMPTCODE_DB_NAME} as ${PROMPTCODE_DB_USER}..."
gunzip -c "${LOCAL_BACKUP}" | docker compose -f "${DEPLOY_DIR}/docker-compose.yml" \
  -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
  exec -T db psql -v ON_ERROR_STOP=1 -U "${PROMPTCODE_DB_USER}" -d "${PROMPTCODE_DB_NAME}"
echo "[restore] Restore complete."
