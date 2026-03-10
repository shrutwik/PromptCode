#!/usr/bin/env bash
# backup-db.sh — Host-level PostgreSQL backup for PromptCode.
#
# Usage:
#   bash /opt/promptcode/scripts/backup-db.sh
#
# Env vars (sourced from /opt/promptcode/.env if not already exported):
#   PROMPTCODE_DB_PASSWORD  — Postgres password (required by pg_dump inside container)
#   PROMPTCODE_DB_USER      — Postgres user (default: promptcode)
#   PROMPTCODE_DB_NAME      — Postgres database name (default: promptcode)
#   BACKUP_DIR              — Where to store backups (default: /opt/promptcode/backups)
#   BACKUP_RETENTION_DAYS   — Number of days to keep local backups (default: 7)
#   RCLONE_REMOTE           — Required rclone remote path (e.g. s3:my-bucket/backups)
#
# To run automatically, add a crontab entry (as the deploy user):
#   0 3 * * * /opt/promptcode/scripts/backup-db.sh >> /opt/promptcode/backups/backup.log 2>&1

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"
BACKUP_DIR="${BACKUP_DIR:-${DEPLOY_DIR}/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/promptcode-${TIMESTAMP}.sql.gz"
LAST_SUCCESS_FILE="${BACKUP_DIR}/last-successful-backup.txt"
LAST_SUCCESS_COMPAT_FILE="${BACKUP_DIR}/.last-success-timestamp"

# Load .env if password not already in environment
if [[ -z "${PROMPTCODE_DB_PASSWORD:-}" && -f "${DEPLOY_DIR}/.env" ]]; then
    # shellcheck disable=SC1090
    set -a; source "${DEPLOY_DIR}/.env"; set +a
fi

PROMPTCODE_DB_USER="${PROMPTCODE_DB_USER:-promptcode}"
PROMPTCODE_DB_NAME="${PROMPTCODE_DB_NAME:-promptcode}"

if [[ -z "${RCLONE_REMOTE:-}" ]]; then
    echo "[backup] RCLONE_REMOTE must be set for off-host backups." >&2
    exit 1
fi

if ! command -v rclone >/dev/null 2>&1; then
    echo "[backup] rclone is required for off-host backups." >&2
    exit 1
fi

mkdir -p "${BACKUP_DIR}"

echo "[backup] Writing ${BACKUP_FILE}..."
docker compose -f "${DEPLOY_DIR}/docker-compose.yml" \
               -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
    exec -T db pg_dump -U "${PROMPTCODE_DB_USER}" "${PROMPTCODE_DB_NAME}" \
    | gzip > "${BACKUP_FILE}"

echo "[backup] Done. Size: $(du -sh "${BACKUP_FILE}" | cut -f1)"

# ── Retention ────────────────────────────────────────────────────────────────
echo "[backup] Pruning backups older than ${BACKUP_RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "promptcode-*.sql.gz" -mtime "+${BACKUP_RETENTION_DAYS}" -delete

# ── Mandatory off-host upload via rclone ─────────────────────────────────────
echo "[backup] Uploading to ${RCLONE_REMOTE}..."
rclone copy "${BACKUP_FILE}" "${RCLONE_REMOTE}"
LAST_SUCCESS_EPOCH="$(date -u +%s)"
printf '%s\n' "${LAST_SUCCESS_EPOCH}" > "${LAST_SUCCESS_FILE}"
printf '%s\n' "${LAST_SUCCESS_EPOCH}" > "${LAST_SUCCESS_COMPAT_FILE}"
echo "[backup] Upload complete."

echo "[backup] Backup complete."
