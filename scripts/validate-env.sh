#!/usr/bin/env sh
# validate-env.sh — keep .env.example aligned with compose-required vars and config aliases.

set -eu

REPO_DIR=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
ENV_FILE="${REPO_DIR}/.env.example"
CONFIG_FILE="${REPO_DIR}/backend/app/core/config.py"
COMPOSE_FILES=""
CUSTOM_COMPOSE=0

append_compose_file() {
  if [ -n "${COMPOSE_FILES}" ]; then
    COMPOSE_FILES="${COMPOSE_FILES}
$1"
  else
    COMPOSE_FILES="$1"
  fi
}

append_compose_file "${REPO_DIR}/docker-compose.yml"
append_compose_file "${REPO_DIR}/docker-compose.prod.yml"

while [ "$#" -gt 0 ]; do
  case "$1" in
    --env-file)
      ENV_FILE="$2"
      shift 2
      ;;
    --config-file)
      CONFIG_FILE="$2"
      shift 2
      ;;
    --compose-file)
      if [ "${CUSTOM_COMPOSE}" -eq 0 ]; then
        COMPOSE_FILES=""
        CUSTOM_COMPOSE=1
      fi
      append_compose_file "$2"
      shift 2
      ;;
    *)
      echo "Usage: $0 [--env-file PATH] [--config-file PATH] [--compose-file PATH ...]" >&2
      exit 2
      ;;
  esac
done

PROMPTCODE_VALIDATE_ENV_FILE="${ENV_FILE}" \
PROMPTCODE_VALIDATE_CONFIG_FILE="${CONFIG_FILE}" \
PROMPTCODE_VALIDATE_COMPOSE_FILES="${COMPOSE_FILES}" \
python3 - <<'PY'
import ast
import os
import re
import sys
from pathlib import Path

ENV_FILE = Path(os.environ["PROMPTCODE_VALIDATE_ENV_FILE"])
CONFIG_FILE = Path(os.environ["PROMPTCODE_VALIDATE_CONFIG_FILE"])
COMPOSE_FILES = [
    Path(raw)
    for raw in os.environ.get("PROMPTCODE_VALIDATE_COMPOSE_FILES", "").splitlines()
    if raw.strip()
]

errors: list[str] = []

for path in [ENV_FILE, CONFIG_FILE, *COMPOSE_FILES]:
    if not path.exists():
        errors.append(f"Missing input file: {path}")

if errors:
    for error in errors:
        print(error, file=sys.stderr)
    sys.exit(1)

env_var_pattern = re.compile(r"^\s*([A-Z][A-Z0-9_]*)=")
compose_var_pattern = re.compile(r"\$\{([A-Z][A-Z0-9_]*)[^}]*\}")
required_var_pattern = re.compile(r"\$\{([A-Z][A-Z0-9_]*)(?::?\?)[^}]*\}")

env_vars = {
    match.group(1)
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines()
    for match in [env_var_pattern.match(line)]
    if match
}

compose_referenced_vars: set[str] = set()
compose_required_vars: set[str] = set()
for compose_file in COMPOSE_FILES:
    contents = compose_file.read_text(encoding="utf-8")
    compose_referenced_vars.update(compose_var_pattern.findall(contents))
    compose_required_vars.update(required_var_pattern.findall(contents))


def literal_strings(node: ast.AST) -> set[str]:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return {node.value}
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: set[str] = set()
        for item in node.elts:
            values.update(literal_strings(item))
        return values
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "AliasChoices":
        values: set[str] = set()
        for arg in node.args:
            values.update(literal_strings(arg))
        return values
    return set()


config_env_vars: set[str] = set()
tree = ast.parse(CONFIG_FILE.read_text(encoding="utf-8"), filename=str(CONFIG_FILE))
for node in tree.body:
    if not isinstance(node, ast.ClassDef) or node.name != "Settings":
        continue
    for item in node.body:
        if not isinstance(item, ast.AnnAssign) or not isinstance(item.target, ast.Name):
            continue
        field_name = item.target.id
        config_env_vars.add(f"PROMPTCODE_{field_name.upper()}")
        if isinstance(item.value, ast.Call) and isinstance(item.value.func, ast.Name) and item.value.func.id == "Field":
            for keyword in item.value.keywords:
                if keyword.arg == "validation_alias":
                    config_env_vars.update(literal_strings(keyword.value))
    break

missing_required = sorted(compose_required_vars - env_vars)
dead_env_vars = sorted(env_vars - compose_referenced_vars - config_env_vars)

if missing_required:
    errors.append(
        ".env.example is missing required compose variables: " + ", ".join(missing_required)
    )
if dead_env_vars:
    errors.append(
        ".env.example contains variables not referenced by compose or config.py: "
        + ", ".join(dead_env_vars)
    )

if errors:
    for error in errors:
        print(error, file=sys.stderr)
    sys.exit(1)

print(
    "Environment contract OK: "
    f"{len(env_vars)} example vars, "
    f"{len(compose_required_vars)} required compose vars, "
    f"{len(config_env_vars)} config env aliases."
)
PY
