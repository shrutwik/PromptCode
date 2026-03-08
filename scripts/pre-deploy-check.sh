#!/usr/bin/env bash
# pre-deploy-check.sh — local repo sanity checks before pushing a deploy candidate.

set -euo pipefail

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)

DOMAIN="${DOMAIN:-api.example.com}"
PROMPTCODE_DB_PASSWORD="${PROMPTCODE_DB_PASSWORD:-predeploy-db-password}"
PROMPTCODE_JWT_SECRET="${PROMPTCODE_JWT_SECRET:-predeploy-jwt-secret-0123456789abcdef}"
PROMPTCODE_SANDBOX_EXECUTOR_TOKEN="${PROMPTCODE_SANDBOX_EXECUTOR_TOKEN:-predeploy-sandbox-secret-0123456789}"
PROMPTCODE_OPENAI_API_KEY="${PROMPTCODE_OPENAI_API_KEY:-predeploy-openai-key}"
PROMPTCODE_METRICS_TOKEN="${PROMPTCODE_METRICS_TOKEN:-predeploy-metrics-token}"

echo "[preflight] Validating environment contract..."
bash "${REPO_DIR}/scripts/validate-env.sh"

echo "[preflight] Validating merged production compose render..."
render_path="$(mktemp)"
trap 'rm -f "${render_path}"' EXIT

env \
    DOMAIN="${DOMAIN}" \
    PROMPTCODE_DB_PASSWORD="${PROMPTCODE_DB_PASSWORD}" \
    PROMPTCODE_JWT_SECRET="${PROMPTCODE_JWT_SECRET}" \
    PROMPTCODE_SANDBOX_EXECUTOR_TOKEN="${PROMPTCODE_SANDBOX_EXECUTOR_TOKEN}" \
    PROMPTCODE_OPENAI_API_KEY="${PROMPTCODE_OPENAI_API_KEY}" \
    PROMPTCODE_METRICS_TOKEN="${PROMPTCODE_METRICS_TOKEN}" \
    docker compose -f "${REPO_DIR}/docker-compose.yml" -f "${REPO_DIR}/docker-compose.prod.yml" config >"${render_path}"

if grep -Eq 'published: "(8000|5433)"|^[[:space:]]+build:' "${render_path}"; then
    echo "[preflight] Merged production compose still exposes dev ports or build contexts." >&2
    grep -En 'published: "(8000|5433)"|^[[:space:]]+build:' "${render_path}" >&2 || true
    exit 1
fi

echo "[preflight] Local pre-deploy checks passed."
