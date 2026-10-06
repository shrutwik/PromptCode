"""Executable architecture boundaries.

The refactor plan in ``docs/architecture-refactor-plan.md`` names module owners and
forbidden dependencies. Prose rules rot; these tests fail when a boundary is
crossed so the next change has to make a deliberate decision.

They are intentionally static (source inspection) so they run in the default
suite without importing the application, a database, or Docker.
"""
from __future__ import annotations

import ast
import re
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
APP = BACKEND / "app"

# The execution host owns the Docker daemon and runs candidate code. It must not
# be able to read or write application state even if it were compromised.
BROKER_MODULE = "app/execution_broker.py"
FORBIDDEN_BROKER_IMPORTS = (
    "app.db.session",
    "app.models",
    "app.services.interview.ai_provider",
    "app.services.interview.ai_budget",
)

# Transport handlers own parsing and status mapping, not storage internals.
FORBIDDEN_ROUTE_IMPORTS = (
    "app.services.interview.storage_ledger",
    "app.services.interview.workspace_quota",
    "docker",
)

# A key that looks like a credential must never be handed to candidate code. The
# local relay's own short-lived proxy token is the single allowed exception: it is
# scoped to one run and reaches no upstream provider.
ALLOWED_CONTAINER_ENV = {
    "PROMPTCODE_LLM_PROXY_URL",
    "PROMPTCODE_LLM_PROXY_TOKEN",
}
SECRET_LIKE_KEY = re.compile(r"(API_KEY|_KEY|PASSWORD|SECRET|_TOKEN)$", re.IGNORECASE)


def _imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            modules.append(node.module)
            modules.extend(f"{node.module}.{alias.name}" for alias in node.names)
    return modules


def _matches(module: str, forbidden: str) -> bool:
    return module == forbidden or module.startswith(forbidden + ".")


def test_broker_cannot_reach_application_state():
    """The credential-free execution host is enforced at startup and by imports."""
    path = BACKEND / BROKER_MODULE
    violations = [
        f"{BROKER_MODULE} imports {module}"
        for module in _imports(path)
        for forbidden in FORBIDDEN_BROKER_IMPORTS
        if _matches(module, forbidden)
    ]
    assert not violations, (
        "The execution broker reached application state; it must receive neither "
        "credentials nor a database session:\n  " + "\n  ".join(sorted(set(violations)))
    )


def test_broker_credential_free_invariant_is_enforced_at_startup():
    """Config must refuse to boot a broker that holds app credentials."""
    text = (APP / "core" / "config.py").read_text(encoding="utf-8")
    assert "Execution broker must not receive database, JWT, signing or provider credentials." in text
    assert "if self.execution_broker_mode:" in text


def _container_env_keys(path: Path) -> set[str]:
    """String keys appearing in ``environment={...}`` literals in a module."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    keys: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        for keyword in node.keywords:
            if keyword.arg != "environment" or not isinstance(keyword.value, ast.Dict):
                continue
            for key in keyword.value.keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    keys.add(key.value)
    return keys


def test_candidate_containers_receive_no_credential_environment():
    """No container started for candidate code may receive a secret-shaped key."""
    violations: list[str] = []
    for path in sorted(APP.rglob("*.py")):
        relative = path.relative_to(BACKEND).as_posix()
        for key in _container_env_keys(path):
            if key in ALLOWED_CONTAINER_ENV or not SECRET_LIKE_KEY.search(key):
                continue
            violations.append(f"{relative}: container environment key {key}")
    assert not violations, (
        "Candidate code was handed a credential-shaped environment variable:\n  "
        + "\n  ".join(sorted(set(violations)))
    )


def test_transport_handlers_do_not_import_storage_internals_or_docker():
    """Routes call services; they do not drive storage accounting or Docker."""
    violations: list[str] = []
    for path in sorted((APP / "api" / "routes").glob("*.py")):
        relative = path.relative_to(BACKEND).as_posix()
        for module in _imports(path):
            for forbidden in FORBIDDEN_ROUTE_IMPORTS:
                if _matches(module, forbidden):
                    violations.append(f"{relative} imports {module}")
    assert not violations, (
        "Transport handlers reached past their service layer:\n  " + "\n  ".join(sorted(set(violations)))
    )
