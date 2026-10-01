"""Interview challenge registry — candidate-safe metadata only."""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]
CHALLENGES_DIR = REPO_ROOT / "challenges"
REGISTRY_PATH = CHALLENGES_DIR / "interview-registry.json"

# Never expose these to candidates via file APIs.
BLOCKED_NAME_FRAGMENTS = (
    "SOLUTION.md",
    "solution.md",
    "_audit_",
    "AUDIT.md",
    "interviewer",
    ".reference",
)


@lru_cache
def load_registry() -> dict[str, Any]:
    data = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
    return data


def list_challenges(
    *, type_filter: str | None = None, stack_filter: str | None = None
) -> list[dict[str, Any]]:
    items = list(load_registry().get("challenges", []))
    if type_filter:
        needle = type_filter.lower()
        items = [c for c in items if needle in str(c.get("type", "")).lower()]
    if stack_filter:
        needle = stack_filter.lower()
        items = [c for c in items if needle in str(c.get("stack", "")).lower()]
    return items


def get_challenge(slug: str) -> dict[str, Any] | None:
    for item in load_registry().get("challenges", []):
        if item.get("slug") == slug:
            return item
    return None


def get_runner_config(slug: str) -> dict[str, Any]:
    """Server-side runner config (image/commands/limits). Never required by frontend."""
    from app.services.interview.runner import normalize_runner_config

    meta = get_challenge(slug) or {}
    return normalize_runner_config(meta, fallback_test_command=meta.get("test_command"))


def challenge_dir(slug: str) -> Path:
    path = (CHALLENGES_DIR / slug).resolve()
    if not str(path).startswith(str(CHALLENGES_DIR.resolve())):
        raise ValueError("Invalid challenge path")
    if not path.is_dir():
        raise FileNotFoundError(slug)
    return path


def is_blocked_path(rel_path: str) -> bool:
    normalized = rel_path.replace("\\", "/").lstrip("./")
    lower = normalized.lower()
    for frag in BLOCKED_NAME_FRAGMENTS:
        if frag.lower() in lower:
            return True
    parts = lower.split("/")
    if "solution.md" in parts:
        return True
    return False


def candidate_readme(slug: str) -> str:
    readme = challenge_dir(slug) / "README.md"
    if not readme.exists():
        return ""
    return readme.read_text(encoding="utf-8")


def interviewer_file_roles(slug: str | None) -> dict[str, list[str]]:
    """
    Server-only file role metadata. Never returned on candidate challenge APIs.

    Prefers optional registry `interviewer` block; otherwise derives from
    entry_files + common noise filenames (does not expose SOLUTION content).
    """
    if not slug:
        return {
            "relevant_files": [],
            "acceptable_supporting": [],
            "intentionally_irrelevant": [],
        }
    meta = get_challenge(slug) or {}
    block = meta.get("interviewer") if isinstance(meta.get("interviewer"), dict) else {}
    relevant = list(block.get("relevant_files") or meta.get("entry_files") or [])
    supporting = list(
        block.get("acceptable_supporting")
        or [p for p in ("tests/", "README.md") if True]
    )
    # Expand supporting defaults: any path under tests/
    if "tests/" not in supporting:
        supporting.append("tests/")
    irrelevant = list(block.get("intentionally_irrelevant") or [])
    if not irrelevant:
        # Heuristic noise names from audit (candidate-visible files only)
        noise_names = {
            "timezoneFormat.ts",
            "auditLog.ts",
            "indexCache.ts",
            "metrics.ts",
            "metrics_stub.py",
            "billing_hooks.py",
            "catalogCopy.ts",
            "promotionCalendar.ts",
            "email_template.py",
            "ledger_export.py",
            "tax_calendar.py",
            "display.py",
            "theme.ts",
        }
        try:
            root = challenge_dir(slug)
            for p in root.rglob("*"):
                if p.is_file() and p.name in noise_names:
                    rel = p.relative_to(root).as_posix()
                    if not is_blocked_path(rel):
                        irrelevant.append(rel)
        except (FileNotFoundError, ValueError):
            pass
    return {
        "relevant_files": relevant,
        "acceptable_supporting": supporting,
        "intentionally_irrelevant": irrelevant,
    }
