"""Isolated editable workspace snapshots for interview sessions.

Layout per session:
  <workspace_root>/<session_id>/          # candidate working copy
  <workspace_root>/<session_id>.starter/  # immutable starter snapshot for diffs

Never mutates source challenges/ or other session directories.
"""

from __future__ import annotations

import os
import fcntl
import shutil
from pathlib import Path

from app.core.config import get_settings
from app.services.interview.registry import (
    BLOCKED_NAME_FRAGMENTS,
    challenge_dir,
    is_blocked_path,
    is_frozen_path,
)

MAX_FILE_BYTES = 1_500_000

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
        # Local: backend/data/interview_workspaces
        # Image: /app/data/interview_workspaces (parents[4] is / and is not writable)
        base = Path(__file__).resolve().parents[3] / "data" / "interview_workspaces"
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
    from app.services.interview.workspace_quota import storage_capacity
    source_bytes = sum(item.stat().st_size for item in src.rglob('*') if item.is_file()
                       and not any(part in SKIP_DIR_NAMES for part in item.relative_to(src).parts)
                       and not is_blocked_path(item.relative_to(src).as_posix()) and not _should_skip(item))
    with storage_capacity(2 * source_bytes):
        if dest.exists():
            shutil.rmtree(dest)
        if starter.exists():
            shutil.rmtree(starter)
        try:
            _copy_candidate_tree(src, dest)
            _copy_candidate_tree(src, starter)
        except Exception:
            shutil.rmtree(dest, ignore_errors=True)
            shutil.rmtree(starter, ignore_errors=True)
            raise
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
        if not p.is_symlink()
        and p.is_file()
        and not is_blocked_path(p.relative_to(starter).as_posix())
    }
    current_files = {
        p.relative_to(current).as_posix(): p
        for p in current.rglob("*")
        if not p.is_symlink()
        and p.is_file()
        and not is_blocked_path(p.relative_to(current).as_posix())
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
    a_path = contained_file(starter, rel_path)
    b_path = contained_file(current, rel_path)
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


def contained_file(workspace: Path, rel_path: str) -> Path:
    """Resolve a candidate path that stays inside the workspace and is not a link."""
    if not rel_path or "\x00" in rel_path:
        raise PermissionError("Path escape blocked")
    raw = rel_path.replace("\\", "/")
    if raw.startswith("/") or raw.startswith("~"):
        raise PermissionError("Path escape blocked")
    parts = [part for part in raw.split("/") if part not in ("", ".")]
    if not parts or any(part == ".." for part in parts):
        raise PermissionError("Path escape blocked")
    root = workspace.resolve()
    current = root
    for part in parts:
        if part in {".", ".."}:
            raise PermissionError("Path escape blocked")
        current = current / part
        if current.is_symlink():
            raise PermissionError("Path escape blocked")
    try:
        current.resolve().relative_to(root)
    except ValueError:
        raise PermissionError("Path escape blocked") from None
    return current


def workspace_has_escape_link(workspace: Path) -> bool:
    """True when a candidate-visible symlink could point the runner or API outside the session."""
    if not workspace.is_dir():
        return False
    for dirpath, dirnames, filenames in os.walk(workspace, followlinks=False):
        base = Path(dirpath)
        kept: list[str] = []
        for name in dirnames:
            candidate = base / name
            if candidate.is_symlink():
                return True
            if name not in SKIP_DIR_NAMES:
                kept.append(name)
        dirnames[:] = kept
        for name in filenames:
            if (base / name).is_symlink():
                return True
    return False


def candidate_write_allowed(workspace: Path, rel_path: str) -> bool:
    if is_blocked_path(rel_path) or is_frozen_path(rel_path):
        return False
    try:
        contained_file(workspace, rel_path)
    except PermissionError:
        return False
    return True


_CONTEXT_SKIP_NAMES = {
    "package.json",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "npm-shrinkwrap.json",
    "tsconfig.json",
    "vitest.config.ts",
    "vite.config.ts",
    "pytest.ini",
    "requirements.txt",
    "pyproject.toml",
    "setup.cfg",
    "setup.py",
    "tox.ini",
    "dockerfile",
    "makefile",
}
_SOURCE_SUFFIXES = {".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs"}


def _is_test_path(rel: str) -> bool:
    name = rel.rsplit("/", 1)[-1].lower()
    rel_l = rel.lower()
    return (
        "/tests/" in f"/{rel_l}"
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def is_question_context_path(rel: str) -> bool:
    """Ticket files the assistant always sees: the question, tests, and source."""
    normalized = rel.replace("\\", "/").strip().lstrip("./")
    if not normalized or is_blocked_path(normalized):
        return False
    name = normalized.rsplit("/", 1)[-1]
    lower = name.lower()
    if lower == "readme.md" or _is_test_path(normalized):
        return True
    if lower in _CONTEXT_SKIP_NAMES or lower.startswith(".env") or lower.endswith(".sh"):
        return False
    return Path(lower).suffix in _SOURCE_SUFFIXES


def question_context_paths(workspace: Path) -> list[str]:
    paths = [
        item["path"]
        for item in list_files(workspace)
        if is_question_context_path(item["path"])
    ]

    def rank(rel: str) -> tuple[int, str]:
        name = rel.rsplit("/", 1)[-1].lower()
        if name == "readme.md":
            return (0, rel)
        if _is_test_path(rel):
            return (1, rel)
        return (2, rel)

    return sorted(paths, key=rank)


def list_files(workspace: Path) -> list[dict]:
    files: list[dict] = []
    if not workspace.exists():
        return files
    for item in sorted(workspace.rglob("*")):
        if item.is_symlink() or not item.is_file():
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
    path = contained_file(workspace, rel_path)
    if not path.is_file():
        raise FileNotFoundError(rel_path)
    if path.stat().st_size > MAX_FILE_BYTES:
        raise ValueError("File too large for editor")
    return path.read_text(encoding="utf-8", errors="replace")


def write_file(workspace: Path, rel_path: str, content: str) -> None:
    # Cross-process lock outside candidate-visible workspace prevents quota races.
    lock_path = Path(str(workspace) + ".upload.lock")
    with lock_path.open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        if Path(str(workspace) + ".submitted").exists():
            raise ValueError("Submission is frozen; start a new attempt to edit")
        _write_file_locked(workspace, rel_path, content)


def _write_file_locked(workspace: Path, rel_path: str, content: str) -> None:
    if len(Path(rel_path).parts) > 16:
        raise ValueError("File path too deep")
    if is_blocked_path(rel_path) or is_frozen_path(rel_path):
        raise PermissionError("File not available")
    if len(content.encode("utf-8")) > MAX_FILE_BYTES:
        raise ValueError("File too large for editor")
    path = contained_file(workspace, rel_path)
    from app.services.interview.workspace_quota import check_upload
    check_upload(workspace, path, len(content.encode("utf-8")))
    from app.services.interview.workspace_quota import storage_capacity
    # Reserve the full write so an existing file replacement also respects free disk.
    with storage_capacity(len(content.encode('utf-8'))):
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.is_symlink():
            raise PermissionError("Path escape blocked")
        path.write_text(content, encoding="utf-8")
