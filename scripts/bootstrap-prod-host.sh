#!/usr/bin/env bash
# bootstrap-prod-host.sh — Idempotent production host setup for PromptCode.
#
# Run once on a fresh Ubuntu/Debian server as root or a sudo user:
#   bash bootstrap-prod-host.sh
#
# What it does:
#   1. Installs Docker Engine + Docker Compose plugin (if absent)
#   2. Creates /opt/promptcode and copies the repo files in
#   3. Creates /opt/promptcode/.env from .env.example if no .env exists yet
#   4. Opens ports 80 and 443 via ufw (if ufw is active)
#   5. Adds the current user to the docker group
#
# After running:
#   1. Edit /opt/promptcode/.env — fill in all required secrets
#   2. cd /opt/promptcode
#   3. IMAGE_TAG=<sha> docker compose -f docker-compose.prod.yml up -d
#
# The CI deploy job (via appleboy/ssh-action) expects:
#   - Docker installed and accessible without sudo for DEPLOY_USER
#   - /opt/promptcode exists and contains docker-compose.prod.yml + docker/Caddyfile.prod
#   - /opt/promptcode/.env is present with all required vars

set -euo pipefail

DEPLOY_DIR="/opt/promptcode"
REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "=== PromptCode production host bootstrap ==="

# ── 1. Docker ────────────────────────────────────────────────────────────────
if ! command -v docker &>/dev/null; then
  echo "Installing Docker..."
  curl -fsSL https://get.docker.com | sh
else
  echo "Docker already installed: $(docker --version)"
fi

if ! docker compose version &>/dev/null; then
  echo "ERROR: Docker Compose plugin not found. Install Docker Desktop or the compose plugin." >&2
  exit 1
fi

# ── 2. Deploy directory ───────────────────────────────────────────────────────
echo "Setting up ${DEPLOY_DIR}..."
mkdir -p "${DEPLOY_DIR}/docker"

# Copy compose files and Caddyfile
cp "${REPO_DIR}/docker-compose.yml"       "${DEPLOY_DIR}/docker-compose.yml"
cp "${REPO_DIR}/docker-compose.prod.yml"  "${DEPLOY_DIR}/docker-compose.prod.yml"
cp "${REPO_DIR}/docker/Caddyfile.prod"    "${DEPLOY_DIR}/docker/Caddyfile.prod"

# ── 3. .env ───────────────────────────────────────────────────────────────────
if [[ ! -f "${DEPLOY_DIR}/.env" ]]; then
  echo "Creating ${DEPLOY_DIR}/.env from .env.example — fill in all required values."
  cp "${REPO_DIR}/.env.example" "${DEPLOY_DIR}/.env"
  chmod 600 "${DEPLOY_DIR}/.env"
else
  echo ".env already exists — skipping (not overwritten)."
fi

# ── 4. Firewall ───────────────────────────────────────────────────────────────
if command -v ufw &>/dev/null && ufw status | grep -q "Status: active"; then
  echo "Opening ports 80 and 443 in ufw..."
  ufw allow 80/tcp
  ufw allow 443/tcp
  ufw allow 443/udp   # HTTP/3
else
  echo "ufw not active — skipping firewall config. Open ports 80 and 443 manually."
fi

# ── 5. Docker group ───────────────────────────────────────────────────────────
CURRENT_USER="${SUDO_USER:-$(whoami)}"
if ! groups "${CURRENT_USER}" | grep -q docker; then
  echo "Adding ${CURRENT_USER} to docker group (re-login required to take effect)."
  usermod -aG docker "${CURRENT_USER}"
fi

echo ""
echo "=== Bootstrap complete ==="
echo "Next steps:"
echo "  1. Edit ${DEPLOY_DIR}/.env — fill in PROMPTCODE_DB_PASSWORD, PROMPTCODE_JWT_SECRET,"
echo "       PROMPTCODE_SANDBOX_EXECUTOR_TOKEN, PROMPTCODE_OPENAI_API_KEY, DOMAIN"
echo "  2. Store a persistent GHCR credential for rollbacks (GITHUB_TOKEN from CI expires):"
echo "       Create a GitHub PAT with read:packages scope, then run:"
echo "       echo <PAT> | docker login ghcr.io -u <github-username> --password-stdin"
echo "  3. cd ${DEPLOY_DIR}"
echo "  4. First deploy is triggered automatically by CI on push to main."
echo "     Manual rollback: IMAGE_TAG=\$(cat ${DEPLOY_DIR}/.previous-image-tag) \\"
echo "       docker compose -f docker-compose.prod.yml up -d"
