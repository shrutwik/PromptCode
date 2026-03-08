#!/usr/bin/env bash
# setup-ghcr-login.sh — ensure the production host can pull GHCR images after restarts and rollbacks.

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"
ENV_FILE="${ENV_FILE:-${DEPLOY_DIR}/.env}"

if [[ -f "${ENV_FILE}" ]]; then
    # shellcheck disable=SC1090
    set -a; source "${ENV_FILE}"; set +a
fi

PUBLIC_IMAGES="$(printf '%s' "${PROMPTCODE_GHCR_PUBLIC_IMAGES:-false}" | tr '[:upper:]' '[:lower:]')"
if [[ "${PUBLIC_IMAGES}" == "1" || "${PUBLIC_IMAGES}" == "true" || "${PUBLIC_IMAGES}" == "yes" || "${PUBLIC_IMAGES}" == "on" ]]; then
    echo "[ghcr] Skipping GHCR login because PROMPTCODE_GHCR_PUBLIC_IMAGES=true."
    exit 0
fi

if [[ -z "${GHCR_USERNAME:-}" ]]; then
    echo "[ghcr] GHCR_USERNAME must be set unless PROMPTCODE_GHCR_PUBLIC_IMAGES=true." >&2
    exit 1
fi

if [[ -z "${GHCR_TOKEN:-}" ]]; then
    echo "[ghcr] GHCR_TOKEN must be set unless PROMPTCODE_GHCR_PUBLIC_IMAGES=true." >&2
    exit 1
fi

printf '%s' "${GHCR_TOKEN}" | docker login ghcr.io -u "${GHCR_USERNAME}" --password-stdin >/dev/null
echo "[ghcr] GHCR login refreshed for ${GHCR_USERNAME}."
