#!/usr/bin/env bash
# Run source retention cleanup inside the app's credentialed environment.
set -euo pipefail
DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"
if [[ -f "${DEPLOY_DIR}/.env" ]]; then
    set -a
    source "${DEPLOY_DIR}/.env"
    set +a
fi
docker compose -f "${DEPLOY_DIR}/docker-compose.yml" \
    -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
    exec -T backend python -m scripts.cleanup_interview_sessions
