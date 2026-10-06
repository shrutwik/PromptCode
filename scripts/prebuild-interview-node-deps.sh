#!/usr/bin/env sh
# Prebuild Node deps for interview runners.
# Installs reviewed challenge dependencies during image builds.
# The runner never runs npm install or pip install during a candidate run.
# docker/Dockerfile.interview-node bakes these into an offline dependency cache.
# Candidate containers must not npm install at run time (network stays off).
# This script is the only place network is allowed for those packages.
# Idempotent: npm ci from package-lock.json, else npm install. Safe to re-run.
# Challenges with no package.json are skipped. Do not commit node_modules.
# Does not change IsolatedRunner security behavior.
# Run: scripts/prebuild-interview-node-deps.sh

set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
CHALLENGES_DIR="${REPO_DIR}/challenges"

if ! command -v npm >/dev/null 2>&1; then
  echo "npm is required to prebuild interview Node dependencies" >&2
  exit 1
fi

found=0
for pkg in "${CHALLENGES_DIR}"/*/package.json; do
  if [ ! -f "${pkg}" ]; then
    continue
  fi
  found=1
  dir=$(dirname -- "${pkg}")
  slug=$(basename -- "${dir}")
  echo "prebuild ${slug}"
  (
    cd -- "${dir}"
    if [ -f package-lock.json ]; then
      npm ci --no-audit --no-fund
    else
      npm install --no-audit --no-fund
    fi
  )
done

if [ "${found}" -eq 0 ]; then
  echo "no Node challenges with package.json"
fi
