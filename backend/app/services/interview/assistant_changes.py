"""Keep assistant claims aligned with files that can actually change."""

from __future__ import annotations

import difflib
import re
from pathlib import Path

from app.services.interview.registry import is_blocked_path, is_frozen_path
from app.services.interview.workspace import MAX_FILE_BYTES, candidate_write_allowed, read_file

_FENCE = re.compile(
    r"```[\w.+-]*\n(?:#|//)\s*file:\s*([^\n]+)\n(.*?)```",
    re.S | re.I,
)
_CLAIM = re.compile(
    r"\b(?:changed|updated|edited|modified|wrote|created|deleted|removed)\b[^\n]{0,160}",
    re.I,
)
_PATH = re.compile(r"[A-Za-z0-9_./-]+\.[A-Za-z0-9]+")


def _norm(path: str) -> str:
    return str(path or "").replace("\\", "/").strip().lstrip("./")


def _unified(path: str, before: str, after: str) -> str:
    lines = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=f"a/{path}",
        tofile=f"b/{path}",
        lineterm="",
    )
    return "\n".join(lines) or "(no text change)"


def reconcile_assistant_proposals(
    *,
    reply: str,
    proposed: list[dict],
    workspace: Path,
) -> tuple[str, list[dict], list[dict]]:
    """Drop protected edits and say so. Nothing here is written."""
    kept: list[dict] = []
    refused: list[dict] = []
    seen: set[str] = set()
    for edit in proposed or []:
        path = _norm((edit or {}).get("path"))
        content = (edit or {}).get("content")
        if not path or path in seen:
            continue
        seen.add(path)
        if not isinstance(content, str):
            refused.append({"path": path, "reason": "The assistant did not include file text."})
            continue
        if len(content.encode("utf-8")) > MAX_FILE_BYTES:
            refused.append({"path": path, "reason": "File too large for editor."})
            continue
        if (
            is_blocked_path(path)
            or is_frozen_path(path)
            or not candidate_write_allowed(workspace, path)
        ):
            refused.append({"path": path, "reason": "This file is read-only."})
            continue
        try:
            before = read_file(workspace, path)
        except FileNotFoundError:
            before = ""
        except (PermissionError, ValueError):
            refused.append({"path": path, "reason": "This file is read-only."})
            continue
        item = {
            "path": path,
            "content": content,
            "before": before,
            "unified": _unified(path, before, content),
        }
        if "base_revision" in (edit or {}):
            item["base_revision"] = edit["base_revision"]
        kept.append(item)

    kept_paths = {item["path"] for item in kept}
    refused_paths = {item["path"] for item in refused}

    def _drop_fence(match: re.Match[str]) -> str:
        path = _norm(match.group(1))
        if path in kept_paths:
            return match.group(0)
        return ""

    cleaned = _FENCE.sub(_drop_fence, reply or "").strip()
    claimed: list[str] = []
    for sentence in _CLAIM.findall(cleaned):
        for path in _PATH.findall(sentence):
            norm = _norm(path)
            if norm and norm not in kept_paths:
                claimed.append(norm)
    claimed = list(dict.fromkeys(claimed))
    # A path mentioned only because it was refused is already explained below.
    claimed = [path for path in claimed if path not in refused_paths]

    parts = [cleaned] if cleaned else []
    if kept:
        parts.append(
            "Proposed files (nothing is written until you accept):\n"
            + "\n".join(f"- {item['path']}" for item in kept)
        )
    if refused:
        parts.append(
            "Refused. These files were not changed:\n"
            + "\n".join(f"- {item['path']}: {item['reason']}" for item in refused)
        )
    if claimed:
        parts.append(
            "The assistant mentioned "
            + ", ".join(claimed)
            + ", but those paths are not in the workspace change list."
        )
    if not kept and not refused:
        parts.append("No files were changed.")
    return "\n\n".join(parts).strip(), kept, refused
