"""Isolated editable workspace snapshots for interview sessions.

Layout per session:
  <workspace_root>/<session_id>/          # candidate working copy
  <workspace_root>/<session_id>.starter/  # immutable starter snapshot for diffs

Never mutates source challenges/ or other session directories.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from app.core.config import get_settings
from app.services.interview.registry import (
    BLOCKED_NAME_FRAGMENTS,
    challenge_dir,
    is_blocked_path,
)

SKIP_DIR_NAMES = {
    "node_modules",
    ".venv",
    "venv",
    "__pycache__",
    ".pytest_cache",
    ".git",
    "dist",
    "build",
    ".turbo",
    "coverage",
}


def workspace_root() -> Path:
    settings = get_settings()
    base = Path(getattr(settings, "interview_workspace_root", "") or "")
    if not base.parts:
        base = Path(__file__).resolve().parents[4] / "backend" / "data" / "interview_workspaces"
    base.mkdir(parents=True, exist_ok=True)
    return base


def starter_snapshot_path(session_id: str) -> Path:
    return workspace_root() / f"{session_id}.starter"


def _should_skip(path: Path) -> bool:
    name = path.name
    if name in SKIP_DIR_NAMES:
        return True
    for frag in BLOCKED_NAME_FRAGMENTS:
        if frag.lower() in name.lower():
            return True
    return False


def _copy_candidate_tree(src: Path, dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        rel = item.relative_to(src).as_posix()
        if any(part in SKIP_DIR_NAMES for part in item.relative_to(src).parts):
            continue
        if is_blocked_path(rel) or _should_skip(item):
            continue
        target = dest / rel
        if item.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif item.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, target)


def create_workspace(session_id: str, slug: str) -> Path:
    """Create isolated session workspace + immutable starter snapshot."""
    src = challenge_dir(slug)
    dest = workspace_root() / session_id
    starter = starter_snapshot_path(session_id)
    if dest.exists():
        shutil.rmtree(dest)
    if starter.exists():
        shutil.rmtree(starter)
    _copy_candidate_tree(src, dest)
    _copy_candidate_tree(src, starter)
    return dest


def assert_session_isolation(session_id: str, challenge_slug: str) -> None:
    """Cheap invariant: session paths must not alias the source challenge tree."""
    src = challenge_dir(challenge_slug).resolve()
    ws = (workspace_root() / session_id).resolve()
    if ws == src or str(ws).startswith(str(src) + "/"):
        raise RuntimeError("Session workspace must not alias challenge source")
    if str(src).startswith(str(ws) + "/"):
        raise RuntimeError("Challenge source must not live under session workspace")


def compute_diff_stats(starter: Path, current: Path) -> dict:
    """Starter vs current file-level additions/deletions (line counts)."""
    files_changed: list[dict] = []
    starter_files = {
        p.relative_to(starter).as_posix(): p
        for p in starter.rglob("*")
        if p.is_file() and not is_blocked_path(p.relative_to(starter).as_posix())
    }
    current_files = {
        p.relative_to(current).as_posix(): p
        for p in current.rglob("*")
        if p.is_file() and not is_blocked_path(p.relative_to(current).as_posix())
    }
    all_paths = sorted(set(starter_files) | set(current_files))
    total_add = 0
    total_del = 0
    for rel in all_paths:
        if any(part in SKIP_DIR_NAMES for part in Path(rel).parts):
            continue
        a = (
            starter_files[rel].read_text(encoding="utf-8", errors="replace").splitlines()
            if rel in starter_files
            else []
        )
        b = (
            current_files[rel].read_text(encoding="utf-8", errors="replace").splitlines()
            if rel in current_files
            else []
        )
        if a == b:
            continue
        from difflib import SequenceMatcher

        additions = 0
        deletions = 0
        for tag, i1, i2, j1, j2 in SequenceMatcher(None, a, b).get_opcodes():
            if tag == "insert":
                additions += j2 - j1
            elif tag == "delete":
                deletions += i2 - i1
            elif tag == "replace":
                additions += j2 - j1
                deletions += i2 - i1
        total_add += additions
        total_del += deletions
        files_changed.append(
            {
                "path": rel,
                "additions": additions,
                "deletions": deletions,
                "status": (
                    "added"
                    if rel not in starter_files
                    else ("deleted" if rel not in current_files else "modified")
                ),
            }
        )
    return {
        "files_changed": files_changed,
        "additions": total_add,
        "deletions": total_del,
        "file_count": len(files_changed),
    }


def unified_diff_for_file(starter: Path, current: Path, rel_path: str) -> str:
    from difflib import unified_diff

    if is_blocked_path(rel_path):
        raise PermissionError("File not available")
    a_path = starter / rel_path
    b_path = current / rel_path
    a = (
        a_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if a_path.is_file()
        else []
    )
    b = (
        b_path.read_text(encoding="utf-8", errors="replace").splitlines(keepends=True)
        if b_path.is_file()
        else []
    )
    return "".join(
        unified_diff(a, b, fromfile=f"a/{rel_path}", tofile=f"b/{rel_path}")
    )


def list_files(workspace: Path) -> list[dict]:
    files: list[dict] = []
    if not workspace.exists():
        return files
    for item in sorted(workspace.rglob("*")):
        if not item.is_file():
            continue
        rel = item.relative_to(workspace).as_posix()
        if is_blocked_path(rel):
            continue
        if any(part in SKIP_DIR_NAMES for part in item.relative_to(workspace).parts):
            continue
        try:
            size = item.stat().st_size
        except OSError:
            size = 0
        files.append({"path": rel, "size": size})
    return files


def read_file(workspace: Path, rel_path: str) -> str:
    if is_blocked_path(rel_path):
        raise PermissionError("File not available")
    path = (workspace / rel_path).resolve()
    if not str(path).startswith(str(workspace.resolve())):
        raise PermissionError("Path escape blocked")
    if not path.is_file():
        raise FileNotFoundError(rel_path)
    # Cap large binaries / lockfiles for editor
    if path.stat().st_size > 1_500_000:
        raise ValueError("File too large for editor")
    return path.read_text(encoding="utf-8", errors="replace")


def write_file(workspace: Path, rel_path: str, content: str) -> None:
    if is_blocked_path(rel_path):
        raise PermissionError("File not available")
    path = (workspace / rel_path).resolve()
    if not str(path).startswith(str(workspace.resolve())):
        raise PermissionError("Path escape blocked")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
