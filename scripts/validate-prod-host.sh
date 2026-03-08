#!/usr/bin/env bash
# validate-prod-host.sh — fail closed if the production host is missing required deploy prerequisites.

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"

if [[ ! -d "${DEPLOY_DIR}" ]]; then
    echo "[host] Missing deploy directory: ${DEPLOY_DIR}" >&2
    exit 1
fi

required_paths=(
    "docker-compose.yml"
    "docker-compose.prod.yml"
    "scripts/backup-db.sh"
    "scripts/restore-db.sh"
    "scripts/check-prod-health.sh"
    "scripts/validate-host-env.sh"
    "scripts/setup-ghcr-login.sh"
)

for relative_path in "${required_paths[@]}"; do
    if [[ ! -f "${DEPLOY_DIR}/${relative_path}" ]]; then
        echo "[host] Missing required deploy file: ${DEPLOY_DIR}/${relative_path}" >&2
        exit 1
    fi
done

if ! command -v docker >/dev/null 2>&1; then
    echo "[host] docker must be installed for production deploys." >&2
    exit 1
fi

docker info >/dev/null
docker compose version >/dev/null

if ! command -v rclone >/dev/null 2>&1; then
    echo "[host] rclone must be installed before deploying so backups can run off-host." >&2
    exit 1
fi

if ! command -v crontab >/dev/null 2>&1; then
    echo "[host] crontab must be available so backup and health-check jobs can be installed." >&2
    exit 1
fi

bash "${DEPLOY_DIR}/scripts/validate-host-env.sh"

cron_entries="$(crontab -l 2>/dev/null || true)"
if ! grep -qF 'backup-db.sh' <<<"${cron_entries}"; then
    echo "[host] Backup cron is missing for the current deploy user." >&2
    exit 1
fi
if ! grep -qF 'check-prod-health.sh' <<<"${cron_entries}"; then
    echo "[host] Health-check cron is missing for the current deploy user." >&2
    exit 1
fi

echo "[host] Production host preflight OK."
