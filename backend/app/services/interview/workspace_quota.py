"""Persistent upload/dependency budgets; candidate execution additionally uses tmpfs.

Capacity admission and the per-session source quota are answered from the
incremental ledger in :mod:`app.services.interview.storage_ledger`, so a save no
longer walks the whole artifact root under a host-wide lock. Measurements are per
workspace (milliseconds) rather than per root (hundreds of milliseconds and
growing). The root walk remains available as the authoritative reconciliation
path via ``refresh_ledger``.
"""
import fcntl
import os
import shutil
from contextlib import contextmanager
from pathlib import Path

from fastapi import HTTPException

from app.core.config import get_settings
from app.services.interview import storage_ledger as ledger

SOURCE_BYTES = 20 * 1024 * 1024
SOURCE_FILES = 1000
DEPENDENCY_BYTES = 128 * 1024 * 1024
DEPENDENCY_FILES = 20000
DEPENDENCY_DIRS = {'node_modules', '.venv', 'venv'}

_CAPACITY_MESSAGE = 'Interview storage capacity reached. Please try again later.'


def retained_bytes(root: Path) -> int:
    """Count all persistent artifacts, including dependencies and frozen source.

    Reconciliation and metrics fallback path only; request paths use the ledger.
    """
    total = 0
    for directory, dirs, entries in os.walk(root, followlinks=False):
        dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
        for name in entries:
            path = Path(directory) / name
            if path.is_symlink():
                continue
            try:
                total += path.stat().st_size
            except FileNotFoundError:  # Cleanup can concurrently remove artifacts.
                continue
    return total


@contextmanager
def storage_capacity(additional_bytes: int):
    """Reserve persistent storage for one write without walking the tree.

    Yields a callable ``reserve(entry, total_bytes, file_count)`` that records the
    measured size of ``entry`` and settles this reservation in one transaction, so
    a written byte is counted exactly once. Call ``reserve(entry, 0)`` for a write
    that retained nothing. Capacity stays fail-closed: a denied reservation raises
    HTTP 507 with ``Retry-After`` before any write happens, and the reservation is
    released if the body raises.
    """
    from app.services.interview.workspace import workspace_root
    root = workspace_root()
    settings = get_settings()
    with (root / '.storage.lock').open('a') as lock:
        # The same lock the offline backup script takes. The critical section is a
        # single ledger write now, not a full artifact-tree walk.
        fcntl.flock(lock, fcntl.LOCK_EX)
        try:
            reservation = ledger.reserve(
                root,
                _reservation_key(),
                workspace_limit_bytes=0,
                workspace_limit_files=0,
                global_limit_bytes=settings.interview_storage_max_bytes,
                min_free_bytes=settings.interview_storage_min_free_bytes,
                additional_bytes=max(0, additional_bytes),
                additional_files=0,
                free_disk_bytes=shutil.disk_usage(root).free,
            )
        except ledger.InsufficientStorage as exc:
            raise HTTPException(507, _CAPACITY_MESSAGE, headers={'Retry-After': '60'}) from exc
    committed = False

    def commit(entry: str, total_bytes: int, file_count: int = 0) -> None:
        nonlocal committed
        committed = True
        ledger.write(root, entry, total_bytes=total_bytes, file_count=file_count,
                     settle_reservation=reservation)

    try:
        yield commit
    except BaseException:
        if not committed:
            ledger.release(root, _reservation_key(), reserved_bytes=reservation)
        raise
    else:
        if not committed:
            # Nothing was recorded: keep the global total conservative instead of
            # silently discarding the reserved bytes.
            ledger.write(root, _reservation_key(), total_bytes=reservation,
                         settle_reservation=reservation)


def _reservation_key() -> str:
    """Uncommitted reservations are aggregated per process role."""
    return '.reservations'


def usage(root: Path):
    """Authoritative walk of one workspace's source budget (rare, bounded path)."""
    source_bytes = source_files = dependency_bytes = dependency_files = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise ValueError('Workspace link blocked')
        dependency = bool(set(Path(directory).relative_to(root).parts) & DEPENDENCY_DIRS)
        for name in files:
            path = Path(directory) / name
            if path.is_symlink():
                raise ValueError('Workspace link blocked')
            size = path.stat().st_size
            if dependency:
                dependency_bytes += size
                dependency_files += 1
            else:
                source_bytes += size
                source_files += 1
            if source_bytes > SOURCE_BYTES or source_files > SOURCE_FILES or dependency_bytes > DEPENDENCY_BYTES or dependency_files > DEPENDENCY_FILES:
                raise ValueError('Session workspace quota exceeded')
    return source_bytes, source_files


def measure_workspace(root) -> tuple[int, int]:
    """Source bytes and files for one workspace, without the dependency budget.

    Never follows a link and never counts dependency trees, so the result is
    comparable with the ledger's per-workspace entry. The ledger database is
    skipped so a workspace root that also holds it cannot count itself.
    """
    ledger_file = Path(root) / ledger.LEDGER_NAME
    source_bytes = 0
    source_files = 0
    for directory, dirs, files in os.walk(root, followlinks=False):
        relative = Path(directory).relative_to(root).parts
        if set(relative) & DEPENDENCY_DIRS:
            dirs[:] = []
            continue
        dirs[:] = [name for name in dirs if not (Path(directory) / name).is_symlink()]
        for name in files:
            path = Path(directory) / name
            if path.is_symlink() or path == ledger_file:
                continue
            try:
                source_bytes += path.stat().st_size
            except FileNotFoundError:
                continue
            source_files += 1
    return source_bytes, source_files


def check_upload(root, path, content_bytes):
    """Enforce the per-session source quota without a per-save root walk.

    Uses the ledger when it already knows this workspace; otherwise measures the
    workspace once and records it so later saves stay O(1). The caller holds the
    per-workspace write lock, so the measurement cannot race another writer.
    """
    artifact_root = _artifact_root()
    workspace_key = Path(root).name
    exists = path.is_file()
    old_size = path.stat().st_size if exists else 0
    measured = ledger.workspace_usage(artifact_root, workspace_key)
    if measured is None:
        source_bytes, source_files = measure_workspace(root)
        ledger.write(artifact_root, workspace_key, total_bytes=source_bytes,
                     file_count=source_files)
        measured = ledger.WorkspaceUsage(bytes=source_bytes, files=source_files)
    if (measured.bytes - old_size + content_bytes > SOURCE_BYTES
            or measured.files + (not exists) > SOURCE_FILES):
        raise ValueError('Session source quota exceeded')


def record_workspace_usage(workspace, *, record: bool = True) -> tuple[int, int]:
    """Measure one workspace and optionally fold it into the ledger.

    Called while the caller still owns the workspace write lock, so the
    measurement describes exactly the state the write produced. Pass
    ``record=False`` to measure only, then record through the reservation
    callable so the byte is counted once.
    """
    source_bytes, source_files = measure_workspace(workspace)
    if record:
        ledger.write(_artifact_root(), Path(workspace).name, total_bytes=source_bytes,
                     file_count=source_files)
    return source_bytes, source_files


def record_snapshot_usage(root, *, record: bool = True) -> tuple[int, int]:
    """Measure a frozen snapshot (or starter) and optionally ledger it."""
    total, files = measure_workspace(root)
    if record:
        ledger.write(_artifact_root(), Path(root).name, total_bytes=total, file_count=files)
    return total, files


def forget_workspace(root) -> None:
    """Subtract a deleted workspace (or snapshot) from the retained total."""
    ledger.forget(_artifact_root(), Path(root).name)


def _artifact_root() -> Path:
    from app.services.interview.workspace import workspace_root
    return workspace_root()


def refresh_ledger(root: Path | None = None):
    """Reconcile the ledger with the filesystem. Safe to run on a schedule."""
    target = root if root is not None else _artifact_root()
    return ledger.reconcile(target, ledger.measure(target))


def ledger_total(root: Path | None = None) -> int:
    """Retained bytes from the ledger, or a single walk when it is unavailable."""
    target = root if root is not None else _artifact_root()
    if not ledger.is_available(target):
        return retained_bytes(target)
    return ledger.total_bytes(target)
