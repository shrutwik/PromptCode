#!/usr/bin/env bash
# notify-alert.sh — Send an operational alert to a configured destination.
#
# There is no alert manager in the deployment, so health/backup/deploy checks had
# no way to reach a human. This script is the single notification transport.
#
# Configuration (all optional; with none set this script is a no-op that reports
# "not configured" so callers never fail because alerting is absent):
#   PROMPTCODE_ALERT_WEBHOOK_URL   HTTPS endpoint; POSTs a JSON body
#   PROMPTCODE_ALERT_COMMAND       Command run with the message appended as $1
#   PROMPTCODE_ALERT_TIMEOUT       Seconds before the webhook attempt gives up (default 10)
#   PROMPTCODE_ALERT_TOPIC         Label included in the payload (default "promptcode")
#
# Usage: notify-alert.sh <severity> <subject> [detail...]
# Exit:  0 when delivered or not configured, 1 when a configured destination failed.

set -euo pipefail

SEVERITY="${1:-warning}"
SUBJECT="${2:-PromptCode alert}"
shift 2 2>/dev/null || true
DETAIL="${*:-}"

TOPIC="${PROMPTCODE_ALERT_TOPIC:-promptcode}"
TIMEOUT="${PROMPTCODE_ALERT_TIMEOUT:-10}"
HOST="$(hostname 2>/dev/null || echo unknown)"
TIMESTAMP="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

MESSAGE="[${TOPIC}] ${SEVERITY}: ${SUBJECT}"
if [[ -n "${DETAIL}" ]]; then
    MESSAGE="${MESSAGE} — ${DETAIL}"
fi

if [[ -n "${PROMPTCODE_ALERT_COMMAND:-}" ]]; then
    # The command may carry arguments; word-split it so "notify --level" works.
    read -r -a ALERT_COMMAND <<<"${PROMPTCODE_ALERT_COMMAND}"
    if "${ALERT_COMMAND[@]}" "${MESSAGE}" "${SEVERITY}" "${SUBJECT}" "${DETAIL}"; then
        echo "[notify] delivered via PROMPTCODE_ALERT_COMMAND"
        exit 0
    fi
    echo "[notify] PROMPTCODE_ALERT_COMMAND failed" >&2
    exit 1
fi

if [[ -n "${PROMPTCODE_ALERT_WEBHOOK_URL:-}" ]]; then
    if ! command -v curl >/dev/null 2>&1; then
        echo "[notify] curl is required for PROMPTCODE_ALERT_WEBHOOK_URL" >&2
        exit 1
    fi
    # python3 builds the JSON so the message cannot break the payload structure.
    PAYLOAD="$(MESSAGE="${MESSAGE}" SEVERITY="${SEVERITY}" SUBJECT="${SUBJECT}" \
        DETAIL="${DETAIL}" HOST="${HOST}" TIMESTAMP="${TIMESTAMP}" TOPIC="${TOPIC}" python3 - <<'PY'
import json
import os

print(json.dumps({
    "topic": os.environ["TOPIC"],
    "severity": os.environ["SEVERITY"],
    "subject": os.environ["SUBJECT"],
    "detail": os.environ["DETAIL"],
    "host": os.environ["HOST"],
    "timestamp": os.environ["TIMESTAMP"],
    "message": os.environ["MESSAGE"],
}))
PY
)"
    if curl --silent --show-error --fail --max-time "${TIMEOUT}" \
        -X POST -H 'Content-Type: application/json' \
        --data "${PAYLOAD}" "${PROMPTCODE_ALERT_WEBHOOK_URL}" >/dev/null; then
        echo "[notify] delivered via PROMPTCODE_ALERT_WEBHOOK_URL"
        exit 0
    fi
    echo "[notify] webhook delivery failed" >&2
    exit 1
fi

echo "[notify] no alert destination configured (set PROMPTCODE_ALERT_WEBHOOK_URL or PROMPTCODE_ALERT_COMMAND)"
exit 0
