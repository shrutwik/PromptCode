#!/usr/bin/env bash
# rehearse-restore.sh — Create known data, back it up, wipe it, restore it, and verify recovery.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-promptcode-restore-${RANDOM}}"
IMAGE_TAG="${IMAGE_TAG:-restore-itest-${RANDOM}}"
WORK_DIR="$(mktemp -d)"
DEPLOY_DIR="${WORK_DIR}/deploy"
BACKUP_REMOTE_DIR="${WORK_DIR}/remote"
BACKUP_DIR="${DEPLOY_DIR}/backups"
FAKE_BIN_DIR="${WORK_DIR}/bin"
DB_USER="${PROMPTCODE_DB_USER:-promptcode}"
DB_NAME="${PROMPTCODE_DB_NAME:-promptcode}"
KNOWN_VALUE="restore-proof-${RANDOM}"

cleanup() {
  COMPOSE_PROJECT_NAME="${PROJECT_NAME}" IMAGE_TAG="${IMAGE_TAG}" docker compose -f "${DEPLOY_DIR}/docker-compose.yml" -f "${DEPLOY_DIR}/docker-compose.prod.yml" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

mkdir -p "${DEPLOY_DIR}/scripts" "${DEPLOY_DIR}/docker" "${BACKUP_REMOTE_DIR}" "${BACKUP_DIR}" "${FAKE_BIN_DIR}"
cp "${REPO_DIR}/docker-compose.yml" "${DEPLOY_DIR}/docker-compose.yml"
cp "${REPO_DIR}/docker-compose.prod.yml" "${DEPLOY_DIR}/docker-compose.prod.yml"
cp "${REPO_DIR}/scripts/backup-db.sh" "${DEPLOY_DIR}/scripts/backup-db.sh"
cp "${REPO_DIR}/scripts/restore-db.sh" "${DEPLOY_DIR}/scripts/restore-db.sh"
chmod +x "${DEPLOY_DIR}/scripts/backup-db.sh" "${DEPLOY_DIR}/scripts/restore-db.sh"

cat > "${DEPLOY_DIR}/.env" <<EOF
DOMAIN=api.example.com
PROMPTCODE_DB_PASSWORD=restore-db-password
PROMPTCODE_JWT_SECRET=restore-jwt-secret-0123456789abcdef
PROMPTCODE_SANDBOX_EXECUTOR_TOKEN=restore-sandbox-secret
PROMPTCODE_OPENAI_API_KEY=sk-live-restore-key
PROMPTCODE_METRICS_TOKEN=restore-metrics-token
RCLONE_REMOTE=${BACKUP_REMOTE_DIR}
PROMPTCODE_DB_USER=${DB_USER}
PROMPTCODE_DB_NAME=${DB_NAME}
EOF

cat > "${FAKE_BIN_DIR}/rclone" <<'EOF'
#!/usr/bin/env bash
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
  copyto)
    src="$1"
    dest="$2"
    mkdir -p "$(dirname "${dest}")"
    cp "${src}" "${dest}"
    ;;
  *)
    echo "Unsupported fake rclone command: ${cmd}" >&2
    exit 1
    ;;
esac
EOF
chmod +x "${FAKE_BIN_DIR}/rclone"

export PATH="${FAKE_BIN_DIR}:${PATH}"
export COMPOSE_PROJECT_NAME="${PROJECT_NAME}"
export IMAGE_TAG="${IMAGE_TAG}"
export DOMAIN="api.example.com"
export PROMPTCODE_DB_PASSWORD="restore-db-password"
export PROMPTCODE_JWT_SECRET="restore-jwt-secret-0123456789abcdef"
export PROMPTCODE_SANDBOX_EXECUTOR_TOKEN="restore-sandbox-secret"
export PROMPTCODE_OPENAI_API_KEY="sk-live-restore-key"
export PROMPTCODE_METRICS_TOKEN="restore-metrics-token"
export RCLONE_REMOTE="${BACKUP_REMOTE_DIR}"
export PROMPTCODE_DB_USER="${DB_USER}"
export PROMPTCODE_DB_NAME="${DB_NAME}"

compose() {
  docker compose -f "${DEPLOY_DIR}/docker-compose.yml" -f "${DEPLOY_DIR}/docker-compose.prod.yml" "$@"
}

echo "[restore-rehearsal] Starting database service..."
compose up -d db

echo "[restore-rehearsal] Waiting for database readiness..."
for i in $(seq 1 24); do
  if compose exec -T db pg_isready -U "${DB_USER}" >/dev/null 2>&1; then
    break
  fi
  sleep 5
done

echo "[restore-rehearsal] Creating known data..."
compose exec -T db psql -v ON_ERROR_STOP=1 -U "${DB_USER}" -d "${DB_NAME}" <<EOF
CREATE TABLE IF NOT EXISTS restore_rehearsal (value text primary key);
TRUNCATE TABLE restore_rehearsal;
INSERT INTO restore_rehearsal(value) VALUES ('${KNOWN_VALUE}');
EOF

echo "[restore-rehearsal] Running backup..."
DEPLOY_DIR="${DEPLOY_DIR}" BACKUP_DIR="${BACKUP_DIR}" bash "${DEPLOY_DIR}/scripts/backup-db.sh"

BACKUP_FILE="$(find "${BACKUP_DIR}" -name 'promptcode-*.sql.gz' | head -n 1)"
if [[ -z "${BACKUP_FILE}" ]]; then
  echo "[restore-rehearsal] Backup file was not created." >&2
  exit 1
fi

echo "[restore-rehearsal] Dropping known data..."
compose exec -T db psql -v ON_ERROR_STOP=1 -U "${DB_USER}" -d "${DB_NAME}" <<EOF
DROP TABLE restore_rehearsal;
EOF

echo "[restore-rehearsal] Restoring backup..."
DEPLOY_DIR="${DEPLOY_DIR}" BACKUP_DIR="${BACKUP_DIR}" RCLONE_REMOTE="${BACKUP_REMOTE_DIR}" bash "${DEPLOY_DIR}/scripts/restore-db.sh" "${BACKUP_FILE}"

RESTORED_VALUE="$(compose exec -T db psql -Atqc "SELECT value FROM restore_rehearsal LIMIT 1;" -U "${DB_USER}" -d "${DB_NAME}" | tr -d '[:space:]')"
if [[ "${RESTORED_VALUE}" != "${KNOWN_VALUE}" ]]; then
  echo "[restore-rehearsal] Expected restored value ${KNOWN_VALUE}, got ${RESTORED_VALUE}." >&2
  exit 1
fi

echo "[restore-rehearsal] Restore rehearsal passed."
