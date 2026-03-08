#!/usr/bin/env bash
# backup-db.sh — Host-level PostgreSQL backup for PromptCode.
#
# Usage:
#   bash /opt/promptcode/scripts/backup-db.sh
#
# Env vars (sourced from /opt/promptcode/.env if not already exported):
#   PROMPTCODE_DB_PASSWORD  — Postgres password (required by pg_dump inside container)
#   BACKUP_DIR              — Where to store backups (default: /opt/promptcode/backups)
#   BACKUP_RETENTION_DAYS   — Number of days to keep local backups (default: 7)
#   RCLONE_REMOTE           — Optional rclone remote path (e.g. s3:my-bucket/backups)
#                             Leave unset or empty to skip off-host upload.
#
# To run automatically, add a crontab entry (as the deploy user):
#   0 3 * * * /opt/promptcode/scripts/backup-db.sh >> /opt/promptcode/backups/backup.log 2>&1

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"
BACKUP_DIR="${BACKUP_DIR:-${DEPLOY_DIR}/backups}"
BACKUP_RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"
BACKUP_FILE="${BACKUP_DIR}/promptcode-${TIMESTAMP}.sql.gz"

# Load .env if password not already in environment
if [[ -z "${PROMPTCODE_DB_PASSWORD:-}" && -f "${DEPLOY_DIR}/.env" ]]; then
    # shellcheck disable=SC1090
    set -a; source "${DEPLOY_DIR}/.env"; set +a
fi

mkdir -p "${BACKUP_DIR}"

echo "[backup] Writing ${BACKUP_FILE}..."
docker compose -f "${DEPLOY_DIR}/docker-compose.yml" \
               -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
    exec -T db pg_dump -U promptcode promptcode \
    | gzip > "${BACKUP_FILE}"

echo "[backup] Done. Size: $(du -sh "${BACKUP_FILE}" | cut -f1)"

# ── Retention ────────────────────────────────────────────────────────────────
echo "[backup] Pruning backups older than ${BACKUP_RETENTION_DAYS} days..."
find "${BACKUP_DIR}" -name "promptcode-*.sql.gz" -mtime "+${BACKUP_RETENTION_DAYS}" -delete

# ── Optional off-host upload via rclone ──────────────────────────────────────
if [[ -n "${RCLONE_REMOTE:-}" ]]; then
    if command -v rclone &>/dev/null; then
        echo "[backup] Uploading to ${RCLONE_REMOTE}..."
        rclone copy "${BACKUP_FILE}" "${RCLONE_REMOTE}"
        echo "[backup] Upload complete."
    else
        echo "[backup] WARNING: RCLONE_REMOTE set but rclone not installed — skipping upload." >&2
    fi
fi

echo "[backup] Backup complete."
