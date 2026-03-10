#!/usr/bin/env bash
# check-prod-health.sh — Cron-friendly production health check for PromptCode.

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"
BACKUP_DIR="${BACKUP_DIR:-${DEPLOY_DIR}/backups}"
LAST_BACKUP_FILE="${BACKUP_DIR}/.last-success-timestamp"
LEGACY_LAST_BACKUP_FILE="${BACKUP_DIR}/last-successful-backup.txt"
LAST_DEPLOY_STATUS_FILE="${DEPLOY_DIR}/.last-deploy-status"
# Workers publish heartbeats every 5s by default and the backend times them out at 30s,
# so 60s gives one full timeout window plus recovery slack before alerting.
MAX_WORKER_HEARTBEAT_AGE_SECONDS="${MAX_WORKER_HEARTBEAT_AGE_SECONDS:-60}"
# Queue depth above 50 implies user-visible backlog on the current single-host topology.
MAX_QUEUE_DEPTH="${MAX_QUEUE_DEPTH:-50}"
# Daily backups run at 03:00; 26h allows one missed window plus a short investigation buffer.
MAX_BACKUP_AGE_SECONDS="${MAX_BACKUP_AGE_SECONDS:-93600}"

if [[ -f "${DEPLOY_DIR}/.env" ]]; then
    # shellcheck disable=SC1090
    set -a; source "${DEPLOY_DIR}/.env"; set +a
fi

PROMPTCODE_DB_USER="${PROMPTCODE_DB_USER:-promptcode}"
PROMPTCODE_DB_NAME="${PROMPTCODE_DB_NAME:-promptcode}"

sql() {
    docker compose -f "${DEPLOY_DIR}/docker-compose.yml" \
                   -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
        exec -T db psql -Atqc "$1" -U "${PROMPTCODE_DB_USER}" -d "${PROMPTCODE_DB_NAME}"
}

METRICS_STATUS_FILE="$(mktemp "${TMPDIR:-/tmp}/promptcode_metrics_status.XXXXXX")"
trap 'rm -f "${METRICS_STATUS_FILE}"' EXIT

echo "[check] Verifying metrics endpoint..."
docker compose -f "${DEPLOY_DIR}/docker-compose.yml" \
               -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
    exec -T backend python -c "import os, urllib.request; token=os.environ.get('PROMPTCODE_METRICS_TOKEN', '').strip(); headers={'Authorization': f'Bearer {token}'} if token else {}; req=urllib.request.Request('http://127.0.0.1:8000/metrics', headers=headers); print(urllib.request.urlopen(req, timeout=5).status)" >"${METRICS_STATUS_FILE}"
METRICS_STATUS="$(tr -d '\n' <"${METRICS_STATUS_FILE}")"
if [[ "${METRICS_STATUS}" != "200" ]]; then
    echo "[check] Metrics scrape failed with status ${METRICS_STATUS}." >&2
    exit 1
fi

WORKER_HEARTBEAT_AGE="$(sql "SELECT COALESCE(MAX(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_seen_at))), 999999) FROM worker_heartbeats;")"
QUEUE_DEPTH="$(sql "SELECT COUNT(*) FROM evaluation_jobs WHERE status IN ('queued','running');")"
LAST_DEPLOY_STATUS="$(cat "${LAST_DEPLOY_STATUS_FILE}" 2>/dev/null || echo 'unknown')"

if [[ -f "${LAST_BACKUP_FILE}" ]]; then
    LAST_BACKUP_EPOCH="$(tr -d '\n' <"${LAST_BACKUP_FILE}")"
elif [[ -f "${LEGACY_LAST_BACKUP_FILE}" ]]; then
    LAST_BACKUP_EPOCH="$(tr -d '\n' <"${LEGACY_LAST_BACKUP_FILE}")"
else
    LAST_BACKUP_EPOCH="0"
fi
NOW_EPOCH="$(date -u +%s)"
BACKUP_AGE="$((NOW_EPOCH - LAST_BACKUP_EPOCH))"

printf '[check] worker_heartbeat_age_seconds=%s queue_depth=%s backup_age_seconds=%s last_deploy_status=%s\n' \
  "${WORKER_HEARTBEAT_AGE}" "${QUEUE_DEPTH}" "${BACKUP_AGE}" "${LAST_DEPLOY_STATUS}"

if awk "BEGIN { exit !(${WORKER_HEARTBEAT_AGE} > ${MAX_WORKER_HEARTBEAT_AGE_SECONDS}) }"; then
    echo "[check] Worker heartbeat age exceeded ${MAX_WORKER_HEARTBEAT_AGE_SECONDS}s." >&2
    exit 1
fi

if (( QUEUE_DEPTH > MAX_QUEUE_DEPTH )); then
    echo "[check] Queue depth ${QUEUE_DEPTH} exceeded ${MAX_QUEUE_DEPTH}." >&2
    exit 1
fi

if (( BACKUP_AGE > MAX_BACKUP_AGE_SECONDS )); then
    echo "[check] Last successful backup is older than ${MAX_BACKUP_AGE_SECONDS}s." >&2
    exit 1
fi

if [[ "${LAST_DEPLOY_STATUS}" != success* && "${LAST_DEPLOY_STATUS}" != rolled_back* ]]; then
    echo "[check] Last deploy status is not healthy: ${LAST_DEPLOY_STATUS}" >&2
    exit 1
fi

echo "[check] Production health check passed."
