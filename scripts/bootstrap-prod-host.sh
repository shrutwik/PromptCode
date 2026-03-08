#!/usr/bin/env bash
# bootstrap-prod-host.sh — Idempotent production host setup for PromptCode.
#
# Run once on a fresh Ubuntu/Debian server as root or a sudo user:
#   bash bootstrap-prod-host.sh
#
# What it does:
#   1. Installs Docker Engine + Docker Compose plugin (if absent)
#   2. Installs rclone (if absent)
#   3. Creates /opt/promptcode and copies the repo files in
#   4. Creates /opt/promptcode/.env from .env.example if no .env exists yet
#   5. Opens ports 80 and 443 via ufw (if ufw is active)
#   6. Adds the current user to the docker group
#   7. Installs a daily backup cron job (03:00) for the deploy user
#
# After running:
#   1. Edit /opt/promptcode/.env — fill in all required secrets
#   2. cd /opt/promptcode
#   3. IMAGE_TAG=<sha> docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build
#
# The CI deploy job (via appleboy/ssh-action) expects:
#   - Docker installed and accessible without sudo for DEPLOY_USER
#   - /opt/promptcode exists and contains docker-compose.prod.yml + docker/Caddyfile.prod
#   - /opt/promptcode/.env is present with all required vars

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"
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

if ! command -v rclone &>/dev/null; then
  if command -v apt-get &>/dev/null; then
    echo "Installing rclone..."
    apt-get update
    apt-get install -y rclone
  else
    echo "ERROR: rclone not found and apt-get is unavailable. Install rclone manually." >&2
    exit 1
  fi
else
  echo "rclone already installed."
fi

# ── 2. Deploy directory ───────────────────────────────────────────────────────
echo "Setting up ${DEPLOY_DIR}..."
mkdir -p "${DEPLOY_DIR}/docker" "${DEPLOY_DIR}/scripts" "${DEPLOY_DIR}/backups"

# Copy compose files, Caddyfile, and operational scripts
cp "${REPO_DIR}/docker-compose.yml"          "${DEPLOY_DIR}/docker-compose.yml"
cp "${REPO_DIR}/docker-compose.prod.yml"     "${DEPLOY_DIR}/docker-compose.prod.yml"
cp "${REPO_DIR}/docker/Caddyfile.prod"       "${DEPLOY_DIR}/docker/Caddyfile.prod"
cp "${REPO_DIR}/scripts/backup-db.sh"        "${DEPLOY_DIR}/scripts/backup-db.sh"
cp "${REPO_DIR}/scripts/restore-db.sh"       "${DEPLOY_DIR}/scripts/restore-db.sh"
cp "${REPO_DIR}/scripts/seed-prod-data.sh"   "${DEPLOY_DIR}/scripts/seed-prod-data.sh"
cp "${REPO_DIR}/scripts/check-prod-health.sh" "${DEPLOY_DIR}/scripts/check-prod-health.sh"
cp "${REPO_DIR}/scripts/validate-host-env.sh" "${DEPLOY_DIR}/scripts/validate-host-env.sh"
cp "${REPO_DIR}/scripts/setup-ghcr-login.sh" "${DEPLOY_DIR}/scripts/setup-ghcr-login.sh"
cp "${REPO_DIR}/scripts/validate-prod-host.sh" "${DEPLOY_DIR}/scripts/validate-prod-host.sh"
chmod +x "${DEPLOY_DIR}/scripts/backup-db.sh"
chmod +x "${DEPLOY_DIR}/scripts/restore-db.sh"
chmod +x "${DEPLOY_DIR}/scripts/seed-prod-data.sh"
chmod +x "${DEPLOY_DIR}/scripts/check-prod-health.sh"
chmod +x "${DEPLOY_DIR}/scripts/validate-host-env.sh"
chmod +x "${DEPLOY_DIR}/scripts/setup-ghcr-login.sh"
chmod +x "${DEPLOY_DIR}/scripts/validate-prod-host.sh"

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
elif [[ "${PROMPTCODE_ALLOW_EXTERNAL_FIREWALL:-false}" =~ ^(1|true|TRUE|yes|YES|on|ON)$ ]]; then
  echo "ufw not active — relying on an external firewall because PROMPTCODE_ALLOW_EXTERNAL_FIREWALL is set."
else
  echo "ERROR: ufw is not active. Enable ufw or rerun with PROMPTCODE_ALLOW_EXTERNAL_FIREWALL=1 if a cloud firewall/security group already restricts ingress." >&2
  exit 1
fi

# ── 5. Docker group ───────────────────────────────────────────────────────────
CURRENT_USER="${SUDO_USER:-$(whoami)}"
if ! groups "${CURRENT_USER}" | grep -q docker; then
  echo "Adding ${CURRENT_USER} to docker group (re-login required to take effect)."
  usermod -aG docker "${CURRENT_USER}"
fi

# ── 6. Backup cron (idempotent) ───────────────────────────────────────────────
# Use 'bash script' explicitly so the cron job works even if the executable bit
# is lost when CI re-syncs backup-db.sh via scp (scp does not preserve perms).
BACKUP_CRON="0 3 * * * bash /opt/promptcode/scripts/backup-db.sh >> /opt/promptcode/backups/backup.log 2>&1"
HEALTH_CHECK_CRON="*/5 * * * * bash /opt/promptcode/scripts/check-prod-health.sh >> /opt/promptcode/backups/health-check.log 2>&1"
if [[ "$(id -u)" -eq 0 ]]; then
  _ct_list()    { crontab -u "${CURRENT_USER}" -l; }
  _ct_install() { crontab -u "${CURRENT_USER}" -; }
else
  _ct_list()    { crontab -l; }
  _ct_install() { crontab -; }
fi
if ! _ct_list 2>/dev/null | grep -qF 'backup-db.sh'; then
  (_ct_list 2>/dev/null || true; echo "${BACKUP_CRON}") | _ct_install
  echo "Backup cron installed for ${CURRENT_USER}: daily at 03:00"
else
  echo "Backup cron already installed for ${CURRENT_USER} — skipping."
fi
if ! _ct_list 2>/dev/null | grep -qF 'check-prod-health.sh'; then
  (_ct_list 2>/dev/null || true; echo "${HEALTH_CHECK_CRON}") | _ct_install
  echo "Health check cron installed for ${CURRENT_USER}: every 5 minutes"
else
  echo "Health check cron already installed for ${CURRENT_USER} — skipping."
fi

echo ""
echo "=== Bootstrap complete ==="
echo "Next steps:"
echo "  1. Edit ${DEPLOY_DIR}/.env — fill in PROMPTCODE_DB_PASSWORD, PROMPTCODE_JWT_SECRET,"
echo "       PROMPTCODE_SANDBOX_EXECUTOR_TOKEN, PROMPTCODE_OPENAI_API_KEY, DOMAIN,"
echo "       PROMPTCODE_METRICS_TOKEN, RCLONE_REMOTE, and either GHCR credentials"
echo "       (GHCR_USERNAME/GHCR_TOKEN) or PROMPTCODE_GHCR_PUBLIC_IMAGES=true"
echo "  2. Validate the host env and configure GHCR pulls:"
echo "       bash ${DEPLOY_DIR}/scripts/validate-host-env.sh"
echo "       bash ${DEPLOY_DIR}/scripts/setup-ghcr-login.sh"
echo "       bash ${DEPLOY_DIR}/scripts/validate-prod-host.sh"
echo "  3. cd ${DEPLOY_DIR}"
echo "  4. First deploy is triggered automatically by CI on push to main."
echo "  5. If ufw is intentionally inactive, rerun bootstrap with PROMPTCODE_ALLOW_EXTERNAL_FIREWALL=1"
echo "       only after confirming your cloud firewall/security group exposes 80/443 and blocks backend/db ports."
echo ""
echo "Rollback procedure:"
echo "  If NO schema migration ran between the broken and previous deploy:"
echo "    IMAGE_TAG=\$(cat ${DEPLOY_DIR}/.previous-image-tag) \\"
echo "      docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build"
echo ""
echo "  If a schema migration DID run, downgrade BEFORE rolling back the image:"
echo "    docker compose -f docker-compose.yml -f docker-compose.prod.yml \\"
echo "      exec backend python -m alembic downgrade -1"
echo "    # Only after the downgrade succeeds, restart the previous image:"
echo "    IMAGE_TAG=\$(cat ${DEPLOY_DIR}/.previous-image-tag) \\"
echo "      docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --no-build"
echo ""
echo "  Check whether a migration ran by comparing alembic history with .previous-image-tag:"
echo "    docker compose -f docker-compose.yml -f docker-compose.prod.yml \\"
echo "      exec backend python -m alembic current"
