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
from urllib.parse import urlparse
import ssl
from pathlib import Path


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


ai_key_name = "DEEPSEEK_API_KEY" if "api.deepseek.com" in os.environ.get("PROMPTCODE_OPENAI_BASE_URL", "") else "PROMPTCODE_OPENAI_API_KEY"

required = [
    "DOMAIN",
    "PROMPTCODE_DB_PASSWORD",
    "PROMPTCODE_JWT_SECRET",
    "PROMPTCODE_SANDBOX_EXECUTOR_TOKEN",
    "PROMPTCODE_EXECUTION_BROKER_URL",
    "PROMPTCODE_GRADING_SIGNING_KEY",
    "PROMPTCODE_INTERVIEW_INTERNAL_TOKEN",
    ai_key_name,
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
if sandbox_token and (len(sandbox_token.encode()) < 32 or looks_like_placeholder(sandbox_token)):
    errors.append("PROMPTCODE_SANDBOX_EXECUTOR_TOKEN must be a non-placeholder secret of at least 32 bytes.")

broker = urlparse(os.environ.get("PROMPTCODE_EXECUTION_BROKER_URL", "").strip())
if (broker.scheme != "https" or not broker.hostname
        or broker.hostname.lower() in {"localhost", "127.0.0.1", "::1"}
        or broker.username or broker.password or broker.query or broker.fragment):
    errors.append("PROMPTCODE_EXECUTION_BROKER_URL must point to the separate execution host over HTTPS.")
for name in ("PROMPTCODE_GRADING_SIGNING_KEY", "PROMPTCODE_INTERVIEW_INTERNAL_TOKEN"):
    value = os.environ.get(name, "").strip()
    if value and (len(value.encode()) < 32 or looks_like_placeholder(value)):
        errors.append(f"{name} must be a non-placeholder secret of at least 32 bytes.")
ca_file = os.environ.get("PROMPTCODE_EXECUTION_BROKER_CA_FILE", "").strip()
if ca_file:
    try:
        # Production Compose mounts the public CA directory at this fixed path.
        # Validate its host-side file rather than requiring that container path
        # to exist on the application machine itself.
        if ca_file.startswith("/etc/promptcode/broker-ca/"):
            env_root = Path(os.environ["PROMPTCODE_VALIDATE_HOST_ENV_FILE"]).resolve().parent
            ca_root = Path(os.environ.get("BROKER_CA_DIR", "docker/broker-ca"))
            if not ca_root.is_absolute():
                ca_root = env_root / ca_root
            relative = Path(ca_file).relative_to("/etc/promptcode/broker-ca")
            ca_path = (ca_root / relative).resolve()
            ca_path.relative_to(ca_root.resolve())
            ca_file = str(ca_path)
        ssl.create_default_context(cafile=ca_file)
    except (OSError, ValueError, ssl.SSLError):
        errors.append("PROMPTCODE_EXECUTION_BROKER_CA_FILE must contain a readable trusted CA bundle.")

openai_key = os.environ.get(ai_key_name, "").strip()
if openai_key and (openai_key.lower().startswith("sk-placeholder") or looks_like_placeholder(openai_key)):
    errors.append(f"{ai_key_name} must be changed from a placeholder value.")

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
