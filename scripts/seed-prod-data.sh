#!/usr/bin/env bash
# seed-prod-data.sh — Idempotently seed PromptCode production challenge data.
# Safe to run repeatedly: it delegates to scripts.seed_challenge, which skips existing slugs.

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"

echo "[seed] Seeding challenge data into the production database..."
docker compose -f "${DEPLOY_DIR}/docker-compose.yml" \
               -f "${DEPLOY_DIR}/docker-compose.prod.yml" \
    exec -T backend python -m scripts.seed_challenge
echo "[seed] Seed complete."
