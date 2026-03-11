#!/usr/bin/env bash
# rehearse-compose-startup.sh — Verify backend readiness without workers, then worker health,
# and prove seed-prod-data.sh remains idempotent when run twice against the same stack.

set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_NAME="${COMPOSE_PROJECT_NAME:-promptcode-startup-${RANDOM}}"
IMAGE_TAG="${IMAGE_TAG:-startup-itest-${RANDOM}}"
BACKEND_IMAGE="ghcr.io/shrutwik/promptcode/backend:${IMAGE_TAG}"
SANDBOX_WORKDIR="${PROMPTCODE_SANDBOX_HOST_WORKDIR:-/tmp/${PROJECT_NAME}_sandbox}"
EXPECTED_CHALLENGE_COUNT="$(find "${REPO_DIR}/challenges" -mindepth 2 -maxdepth 2 -name challenge.json | wc -l | tr -d ' ')"

cleanup() {
  COMPOSE_PROJECT_NAME="${PROJECT_NAME}" IMAGE_TAG="${IMAGE_TAG}" docker compose -f "${REPO_DIR}/docker-compose.yml" -f "${REPO_DIR}/docker-compose.prod.yml" down -v --remove-orphans >/dev/null 2>&1 || true
  rm -rf "${SANDBOX_WORKDIR}"
}
trap cleanup EXIT

export COMPOSE_PROJECT_NAME="${PROJECT_NAME}"
export IMAGE_TAG="${IMAGE_TAG}"
export DOMAIN="${DOMAIN:-api.example.com}"
export PROMPTCODE_DB_PASSWORD="${PROMPTCODE_DB_PASSWORD:-integration-db-password}"
export PROMPTCODE_JWT_SECRET="${PROMPTCODE_JWT_SECRET:-integration-jwt-secret-0123456789abcdef}"
export PROMPTCODE_SANDBOX_EXECUTOR_TOKEN="${PROMPTCODE_SANDBOX_EXECUTOR_TOKEN:-integration-sandbox-secret}"
export PROMPTCODE_OPENAI_API_KEY="${PROMPTCODE_OPENAI_API_KEY:-sk-live-integration-key}"
export PROMPTCODE_METRICS_TOKEN="${PROMPTCODE_METRICS_TOKEN:-integration-metrics-token}"
export PROMPTCODE_SANDBOX_HOST_WORKDIR="${SANDBOX_WORKDIR}"

mkdir -p "${SANDBOX_WORKDIR}"

docker build -f "${REPO_DIR}/docker/Dockerfile.backend" -t "${BACKEND_IMAGE}" "${REPO_DIR}"
docker build -f "${REPO_DIR}/docker/Dockerfile.sandbox" -t promptcode-sandbox:latest "${REPO_DIR}"

compose() {
  docker compose -f "${REPO_DIR}/docker-compose.yml" -f "${REPO_DIR}/docker-compose.prod.yml" "$@"
}

dump_startup_context() {
  echo "[startup] Current compose service status:" >&2
  compose ps >&2 || true
  echo "[startup] Recent backend-related logs:" >&2
  compose logs --tail=100 backend sandbox-executor db >&2 || true
}

wait_for_http_ready() {
  local service_url="$1"
  local label="$2"
  local attempts="${3:-30}"
  local sleep_seconds="${4:-5}"
  local i
  for i in $(seq 1 "${attempts}"); do
    if compose exec -T backend python -c "import urllib.request; urllib.request.urlopen('${service_url}', timeout=5).read()"; then
      echo "[startup] ${label} is ready."
      return 0
    fi
    echo "[startup] Waiting for ${label} (${i}/${attempts})..."
    sleep "${sleep_seconds}"
  done
  echo "[startup] ${label} did not become ready." >&2
  dump_startup_context
  return 1
}

wait_for_health() {
  local service="$1"
  local attempts="${2:-24}"
  local sleep_seconds="${3:-5}"
  local container_id status i
  for i in $(seq 1 "${attempts}"); do
    container_id="$(compose ps -q "${service}")"
    if [[ -n "${container_id}" ]]; then
      status="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "${container_id}")"
      if [[ "${status}" == "healthy" ]]; then
        echo "[startup] ${service} is healthy."
        return 0
      fi
      if [[ "${status}" == "exited" || "${status}" == "dead" ]]; then
        echo "[startup] ${service} failed with status ${status}." >&2
        compose logs --tail=50 "${service}" >&2 || true
        return 1
      fi
    fi
    echo "[startup] Waiting for ${service} health (${i}/${attempts})..."
    sleep "${sleep_seconds}"
  done
  echo "[startup] ${service} never reached healthy state." >&2
  compose logs --tail=50 "${service}" >&2 || true
  return 1
}

echo "[startup] Bringing up backend without workers..."
compose up -d db sandbox sandbox-executor backend
wait_for_http_ready "http://127.0.0.1:8000/ready" "backend /ready without workers"

echo "[startup] Bringing up workers..."
compose up -d worker worker-b
wait_for_health worker
wait_for_health worker-b

echo "[startup] Verifying seed-prod-data.sh idempotency..."
DEPLOY_DIR="${REPO_DIR}" bash "${REPO_DIR}/scripts/seed-prod-data.sh"
COUNT_AFTER_FIRST="$(compose exec -T db psql -Atqc 'SELECT COUNT(*) FROM challenges;' -U "${PROMPTCODE_DB_USER:-promptcode}" -d "${PROMPTCODE_DB_NAME:-promptcode}" | tr -d '[:space:]')"
DEPLOY_DIR="${REPO_DIR}" bash "${REPO_DIR}/scripts/seed-prod-data.sh"
COUNT_AFTER_SECOND="$(compose exec -T db psql -Atqc 'SELECT COUNT(*) FROM challenges;' -U "${PROMPTCODE_DB_USER:-promptcode}" -d "${PROMPTCODE_DB_NAME:-promptcode}" | tr -d '[:space:]')"

if [[ "${COUNT_AFTER_FIRST}" != "${EXPECTED_CHALLENGE_COUNT}" ]]; then
  echo "[startup] Expected ${EXPECTED_CHALLENGE_COUNT} seeded challenges after first run, got ${COUNT_AFTER_FIRST}." >&2
  exit 1
fi
if [[ "${COUNT_AFTER_SECOND}" != "${COUNT_AFTER_FIRST}" ]]; then
  echo "[startup] Challenge count changed after second seed run (${COUNT_AFTER_FIRST} -> ${COUNT_AFTER_SECOND})." >&2
  exit 1
fi

echo "[startup] Startup graph and seed idempotency rehearsal passed."
