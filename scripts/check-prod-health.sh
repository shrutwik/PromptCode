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

# Disk reserve below this is an operational emergency: writes start failing closed
# with 507 and the documented remedy is manual storage expansion.
MIN_FREE_DISK_BYTES="${MIN_FREE_DISK_BYTES:-$((2 * 1024 * 1024 * 1024))}"

if [[ -f "${DEPLOY_DIR}/.env" ]]; then
    # shellcheck disable=SC1090
    set -a; source "${DEPLOY_DIR}/.env"; set +a
fi
MAX_GRADING_QUEUE_AGE_SECONDS="${MAX_GRADING_QUEUE_AGE_SECONDS:-${PROMPTCODE_GRADING_QUEUE_ALERT_SECONDS:-300}}"
GRADING_FAILED_ALERT_JOBS="${PROMPTCODE_GRADING_FAILED_ALERT_JOBS:-1}"
MAX_GRADING_FAILED_JOBS="${MAX_GRADING_FAILED_JOBS:-$((GRADING_FAILED_ALERT_JOBS - 1))}"
if [[ -n "${PROMPTCODE_INTERVIEW_STORAGE_MIN_FREE_BYTES:-}" ]]; then
    MIN_FREE_DISK_BYTES="${MIN_FREE_DISK_BYTES:-${PROMPTCODE_INTERVIEW_STORAGE_MIN_FREE_BYTES}}"
fi

PROMPTCODE_DB_USER="${PROMPTCODE_DB_USER:-promptcode}"
PROMPTCODE_DB_NAME="${PROMPTCODE_DB_NAME:-promptcode}"

sql() {
    docker compose -f "${DEPLOY_DIR}/docker-compose.yml" \
                   -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
        exec -T db psql -Atqc "$1" -U "${PROMPTCODE_DB_USER}" -d "${PROMPTCODE_DB_NAME}"
}

# Reports the oldest heartbeat age (so a wedged fleet is still caught) alongside
# the number of workers whose own heartbeat is stale. A global MAX alone hides one
# dead worker among healthy replicas.
read -r WORKER_HEARTBEAT_AGE STALE_WORKERS < <(
    sql "SELECT COALESCE(MAX(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_seen_at))), 999999), \
COUNT(*) FILTER (WHERE CURRENT_TIMESTAMP - last_seen_at > make_interval(secs => ${MAX_WORKER_HEARTBEAT_AGE_SECONDS})) \
FROM worker_heartbeats;" | tr -s ' ' | tr '|' ' '
)
STALE_WORKERS="${STALE_WORKERS:-0}"

METRICS_STATUS_FILE="$(mktemp "${TMPDIR:-/tmp}/promptcode_metrics_status.XXXXXX")"
trap 'rm -f "${METRICS_STATUS_FILE}"' EXIT

echo "[check] Verifying metrics endpoint..."
docker compose -f "${DEPLOY_DIR}/docker-compose.yml" \
               -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
    exec -T backend python -c "import os, urllib.request; token=os.environ.get('PROMPTCODE_METRICS_TOKEN', '').strip(); headers={'Authorization': f'Bearer {token}'} if token else {}; req=urllib.request.Request('http://127.0.0.1:8000/metrics', headers=headers); body=urllib.request.urlopen(req, timeout=5).read().decode(); print('status=' + str(200)); print(body)" >"${METRICS_STATUS_FILE}"
METRICS_STATUS="$(grep -m1 '^status=' "${METRICS_STATUS_FILE}" | cut -d= -f2- || true)"
if [[ -z "${METRICS_STATUS}" ]]; then
    # A probe that only prints the status code (as the contract tests do) still works.
    METRICS_STATUS="$(tr -d '[:space:]' <"${METRICS_STATUS_FILE}")"
fi
if [[ "${METRICS_STATUS}" != "200" ]]; then
    echo "[check] Metrics scrape failed with status ${METRICS_STATUS:-none}." >&2
    exit 1
fi
# The retained-storage gauge is the only disk signal; a full artifact volume makes
# uploads, submissions and grading fail closed, and the documented remedy is manual.
FREE_DISK_BYTES="$(grep -m1 '^promptcode_interview_storage_free_bytes ' "${METRICS_STATUS_FILE}" | awk '{print $2}' || true)"
FREE_DISK_BYTES="${FREE_DISK_BYTES%%.*}"

WORKER_HEARTBEAT_AGE="$(sql "SELECT COALESCE(MAX(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - last_seen_at))), 999999) FROM worker_heartbeats;")"
QUEUE_DEPTH="$(sql "SELECT COUNT(*) FROM evaluation_jobs WHERE status IN ('queued','running');")"
GRADING_QUEUE_DEPTH="$(sql "SELECT COUNT(*) FROM interview_grading_jobs WHERE status IN ('queued','running');")"
GRADING_FAILED="$(sql "SELECT COUNT(*) FROM interview_grading_jobs WHERE status='failed';")"
GRADING_STALE="$(sql "SELECT COUNT(*) FROM interview_grading_jobs WHERE status='running' AND lease_expires_at <= CURRENT_TIMESTAMP;")"
GRADING_QUEUE_AGE="$(sql "SELECT COALESCE(EXTRACT(EPOCH FROM (CURRENT_TIMESTAMP - MIN(created_at))),0) FROM interview_grading_jobs WHERE status='queued';")"
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


# Every failure path reports to the configured alert destination before exiting.
# A missing destination is a no-op so health checking never depends on alerting.
NOTIFY_SCRIPT="${NOTIFY_SCRIPT:-$(dirname "${BASH_SOURCE[0]}")/notify-alert.sh}"
fail() {
    local reason="$1"
    local detail="${2:-}"
    echo "[check] ${reason}" >&2
    if [[ -x "${NOTIFY_SCRIPT}" ]]; then
        bash "${NOTIFY_SCRIPT}" critical "${reason}" "${detail}" >/dev/null 2>&1 || true
    fi
    exit 1
}

printf '[check] worker_heartbeat_age_seconds=%s stale_workers=%s queue_depth=%s backup_age_seconds=%s last_deploy_status=%s\n' \
  "${WORKER_HEARTBEAT_AGE}" "${STALE_WORKERS}" "${QUEUE_DEPTH}" "${BACKUP_AGE}" "${LAST_DEPLOY_STATUS}"
printf '[check] grading_pending=%s grading_failed=%s grading_stale_leases=%s grading_oldest_queued_seconds=%s free_disk_bytes=%s\n' \
  "${GRADING_QUEUE_DEPTH}" "${GRADING_FAILED}" "${GRADING_STALE}" "${GRADING_QUEUE_AGE}" "${FREE_DISK_BYTES:-unknown}"

if (( GRADING_QUEUE_DEPTH > MAX_QUEUE_DEPTH || GRADING_FAILED > MAX_GRADING_FAILED_JOBS || GRADING_STALE > 0 )) \
  || awk "BEGIN { exit !(${GRADING_QUEUE_AGE} > ${MAX_GRADING_QUEUE_AGE_SECONDS}) }"; then
    fail "Grading backlog, failed job, or expired lease requires attention." \
        "pending=${GRADING_QUEUE_DEPTH} failed=${GRADING_FAILED} stale_leases=${GRADING_STALE} oldest_queued_seconds=${GRADING_QUEUE_AGE}"
fi

if awk "BEGIN { exit !(${WORKER_HEARTBEAT_AGE} > ${MAX_WORKER_HEARTBEAT_AGE_SECONDS}) }"; then
    fail "Worker heartbeat age exceeded ${MAX_WORKER_HEARTBEAT_AGE_SECONDS}s." \
        "oldest_heartbeat_age_seconds=${WORKER_HEARTBEAT_AGE}"
fi

# A single dead worker among healthy replicas is invisible to a global MAX.
if [[ -n "${STALE_WORKERS}" ]] && (( STALE_WORKERS > 0 )); then
    fail "${STALE_WORKERS} worker(s) have a stale heartbeat (older than ${MAX_WORKER_HEARTBEAT_AGE_SECONDS}s)." \
        "stale_workers=${STALE_WORKERS}"
fi

if [[ -n "${FREE_DISK_BYTES}" ]] && (( FREE_DISK_BYTES < MIN_FREE_DISK_BYTES )); then
    fail "Free disk ${FREE_DISK_BYTES} is below the ${MIN_FREE_DISK_BYTES}-byte reserve; writes will fail closed." \
        "free_disk_bytes=${FREE_DISK_BYTES} min_free_disk_bytes=${MIN_FREE_DISK_BYTES}"
fi

if (( QUEUE_DEPTH > MAX_QUEUE_DEPTH )); then
    fail "Queue depth ${QUEUE_DEPTH} exceeded ${MAX_QUEUE_DEPTH}." "queue_depth=${QUEUE_DEPTH}"
fi

if (( BACKUP_AGE > MAX_BACKUP_AGE_SECONDS )); then
    fail "Last successful backup is older than ${MAX_BACKUP_AGE_SECONDS}s." "backup_age_seconds=${BACKUP_AGE}"
fi

if [[ "${LAST_DEPLOY_STATUS}" != success* && "${LAST_DEPLOY_STATUS}" != rolled_back* ]]; then
    fail "Last deploy status is not healthy: ${LAST_DEPLOY_STATUS}" "last_deploy_status=${LAST_DEPLOY_STATUS}"
fi

echo "[check] Production health check passed."
