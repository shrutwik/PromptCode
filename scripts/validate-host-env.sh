#!/usr/bin/env bash
# validate-host-env.sh — fail closed if the production host .env is incomplete or unsafe.

set -euo pipefail

DEPLOY_DIR="${DEPLOY_DIR:-/opt/promptcode}"
ENV_FILE="${ENV_FILE:-${DEPLOY_DIR}/.env}"

if [[ ! -f "${ENV_FILE}" ]]; then
    echo "[env] Missing host env file: ${ENV_FILE}" >&2
    exit 1
fi

# shellcheck disable=SC1090
set -a; source "${ENV_FILE}"; set +a

PROMPTCODE_VALIDATE_HOST_ENV_FILE="${ENV_FILE}" python3 - <<'PY'
import os
import sys


_PLACEHOLDER_NORMALIZED_VALUES = {
    "",
    "changeme",
    "password",
    "placeholder",
    "promptcode",
    "replaceme",
    "replaceit",
    "replacethiswitharandomsecret",
    "replacethiswithalongrandomsecret",
    "skplaceholder",
    "skyourkeyhere",
}


def normalize(value: str) -> str:
    return "".join(char for char in value.lower() if char.isalnum())


def looks_like_placeholder(value: str) -> bool:
    return normalize(value) in _PLACEHOLDER_NORMALIZED_VALUES


def is_truthy(value: str) -> bool:
    return value.strip().lower() in {"1", "true", "yes", "on"}


required = [
    "DOMAIN",
    "PROMPTCODE_DB_PASSWORD",
    "PROMPTCODE_JWT_SECRET",
    "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN",
    "PROMPTCODE_OPENAI_API_KEY",
    "PROMPTCODE_METRICS_TOKEN",
    "RCLONE_REMOTE",
]

errors: list[str] = []

for name in required:
    if not os.environ.get(name, "").strip():
        errors.append(f"{name} must be set in the host .env.")

domain = os.environ.get("DOMAIN", "").strip()
if domain.lower() in {"localhost", "127.0.0.1", "::1"} or domain.lower().startswith(
    ("localhost:", "127.0.0.1:", "[::1]:")
):
    errors.append("DOMAIN must not point at localhost in the host .env.")

jwt_secret = os.environ.get("PROMPTCODE_JWT_SECRET", "").strip()
if jwt_secret and (len(jwt_secret) < 32 or looks_like_placeholder(jwt_secret)):
    errors.append("PROMPTCODE_JWT_SECRET must be a non-placeholder secret with at least 32 characters.")

db_password = os.environ.get("PROMPTCODE_DB_PASSWORD", "").strip()
if db_password and looks_like_placeholder(db_password):
    errors.append("PROMPTCODE_DB_PASSWORD must be changed from the development default or a placeholder.")

sandbox_token = os.environ.get("PROMPTCODE_SANDBOX_EXECUTOR_TOKEN", "").strip()
if sandbox_token and looks_like_placeholder(sandbox_token):
    errors.append("PROMPTCODE_SANDBOX_EXECUTOR_TOKEN must be changed from a placeholder value.")

openai_key = os.environ.get("PROMPTCODE_OPENAI_API_KEY", "").strip()
if openai_key and (openai_key.lower().startswith("sk-placeholder") or looks_like_placeholder(openai_key)):
    errors.append("PROMPTCODE_OPENAI_API_KEY must be changed from a placeholder value.")

metrics_token = os.environ.get("PROMPTCODE_METRICS_TOKEN", "").strip()
if metrics_token and looks_like_placeholder(metrics_token):
    errors.append("PROMPTCODE_METRICS_TOKEN must be changed from a placeholder value.")

public_images = is_truthy(os.environ.get("PROMPTCODE_GHCR_PUBLIC_IMAGES", "false"))
ghcr_username = os.environ.get("GHCR_USERNAME", "").strip()
ghcr_token = os.environ.get("GHCR_TOKEN", "").strip()
if not public_images:
    if not ghcr_username:
        errors.append(
            "GHCR_USERNAME must be set unless PROMPTCODE_GHCR_PUBLIC_IMAGES=true."
        )
    if not ghcr_token:
        errors.append(
            "GHCR_TOKEN must be set unless PROMPTCODE_GHCR_PUBLIC_IMAGES=true."
        )

if errors:
    print("Invalid host environment:", file=sys.stderr)
    for error in dict.fromkeys(errors):
        print(f"- {error}", file=sys.stderr)
    raise SystemExit(1)

print(
    "Host environment OK: "
    f"{len(required)} required values set, "
    + ("GHCR auth skipped (public images)." if public_images else "GHCR credentials configured.")
)
PY
