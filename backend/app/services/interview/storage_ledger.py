"""Persistent, incremental accounting for retained interview artifacts.

Every workspace create, file save and submission freeze used to walk the entire
artifact root under one host-wide exclusive lock (``retained_bytes``), which made
per-request cost grow with total retained bytes and serialized all writers. This
module keeps an atomic ledger so capacity admission is O(1).

Semantics (one writer per quantity, so nothing can be double-counted):

* ``reserve``/``release``/``settle`` move *headroom* in and out of the reserved
  bucket. They never decide what was retained.
* ``record`` is the single writer of retained bytes. It stores the measured size
  of one entry (a session workspace, a starter, a frozen snapshot) and adjusts the
  global total by that entry's change. Callers invoke it once after a write; a
  failed write leaves the previous measurement in place, which is corrected by the
  next write or by ``reconcile``.

Ownership: this ledger is **derived state**. If it is ever wrong, ``reconcile``
rebuilds it from the filesystem, which stays authoritative. No candidate data or
grading evidence lives here.

Cross-process safety: SQLite in WAL mode with ``BEGIN IMMEDIATE`` per mutation.
The application and every worker must share the same artifact root, exactly as
they already must share the workspace lock and ``.storage.lock``.
"""

from __future__ import annotations

import os
import shutil
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

LEDGER_NAME = ".storage-ledger.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS workspace_usage (
    workspace TEXT PRIMARY KEY,
    total_bytes INTEGER NOT NULL,
    file_count INTEGER NOT NULL DEFAULT 0,
    reserved_bytes INTEGER NOT NULL DEFAULT 0,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS global_usage (
    id INTEGER PRIMARY KEY CHECK (id = 1),
    total_bytes INTEGER NOT NULL,
    reserved_bytes INTEGER NOT NULL DEFAULT 0
);
INSERT OR IGNORE INTO global_usage (id, total_bytes, reserved_bytes) VALUES (1, 0, 0);
"""

_thread_lock = threading.Lock()


class InsufficientStorage(RuntimeError):
    """Raised when a reservation would exceed a configured capacity bound."""


@dataclass(frozen=True)
class StorageSnapshot:
    total_bytes: int
    reserved_bytes: int
    workspaces: int

    @property
    def committed_bytes(self) -> int:
        """Retained bytes excluding headroom that is merely reserved."""
        return self.total_bytes


@dataclass(frozen=True)
class WorkspaceUsage:
    bytes: int
    files: int


def _ledger_path(root: Path) -> Path:
    return root / LEDGER_NAME


def _connect(root: Path) -> sqlite3.Connection:
    root.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(str(_ledger_path(root)), timeout=15.0, isolation_level=None)
    connection.execute("PRAGMA journal_mode=WAL")
    connection.execute("PRAGMA synchronous=NORMAL")
    connection.execute("PRAGMA busy_timeout=15000")
    connection.executescript(_SCHEMA)
    return connection


def is_available(root: Path) -> bool:
    """Whether the ledger exists (used to pick the fast path)."""
    return _ledger_path(root).is_file()


def is_writable(root: Path) -> bool:
    """Whether this process may update the ledger.

    The API owns artifact writes; grading workers mount the same root read-only.
    A worker must not keep failing to reconcile (or create a stray ledger next to
    a read-only mount), so callers check this before attempting an update.
    """
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError:
        return False
    return os.access(root, os.W_OK)


def snapshot(root: Path) -> StorageSnapshot:
    """Current retained and reserved bytes without walking the filesystem.

    ``total_bytes`` is committed retained bytes and ``reserved_bytes`` is headroom
    held by in-flight writes; effective usage is their sum, which is what
    ``reserve`` compares against the configured bound.
    """
    with _thread_lock, _connect(root) as connection:
        total, reserved, workspaces = connection.execute(
            "SELECT total_bytes, reserved_bytes,"
            " (SELECT COUNT(*) FROM workspace_usage) FROM global_usage WHERE id = 1"
        ).fetchone()
    return StorageSnapshot(total_bytes=int(total or 0), reserved_bytes=int(reserved or 0),
                           workspaces=int(workspaces or 0))


def total_bytes(root: Path) -> int:
    """Retained bytes including outstanding reservations."""
    current = snapshot(root)
    return current.total_bytes + current.reserved_bytes


def workspace_usage(root: Path, workspace: str) -> WorkspaceUsage | None:
    """Ledgered bytes/files for one workspace, or None when never recorded."""
    key = str(workspace)
    with _thread_lock, _connect(root) as connection:
        row = connection.execute(
            "SELECT total_bytes + reserved_bytes, file_count FROM workspace_usage WHERE workspace = ?",
            (key,),
        ).fetchone()
    return WorkspaceUsage(bytes=int(row[0]), files=int(row[1])) if row else None


def reserve(
    root: Path,
    key: str,
    *,
    workspace_limit_bytes: int,
    workspace_limit_files: int,
    global_limit_bytes: int,
    min_free_bytes: int,
    additional_bytes: int,
    additional_files: int,
    free_disk_bytes: int | None = None,
) -> int:
    """Atomically reserve headroom or raise :class:`InsufficientStorage`.

    ``workspace_limit_bytes`` of zero means the global bound is the only
    per-key budget. ``free_disk_bytes`` lets the caller own the disk probe.
    """
    reserved_key = str(key)
    wanted = max(0, int(additional_bytes))
    wanted_files = max(0, int(additional_files))
    with _thread_lock, _connect(root) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                "SELECT total_bytes, file_count, reserved_bytes FROM workspace_usage WHERE workspace = ?",
                (reserved_key,),
            ).fetchone()
            used = (int(row[0]) + int(row[2])) if row else 0
            used_files = int(row[1]) if row else 0
            if workspace_limit_bytes and used + wanted > workspace_limit_bytes:
                raise InsufficientStorage("Session source quota exceeded")
            if workspace_limit_files and used_files + wanted_files > workspace_limit_files:
                raise InsufficientStorage("Session source quota exceeded")
            total, reserved = connection.execute(
                "SELECT total_bytes, reserved_bytes FROM global_usage WHERE id = 1"
            ).fetchone()
            if global_limit_bytes and int(total) + int(reserved) + wanted > global_limit_bytes:
                raise InsufficientStorage("Interview storage capacity reached")
            free = free_disk_bytes if free_disk_bytes is not None else shutil.disk_usage(root).free
            if free - wanted < min_free_bytes:
                raise InsufficientStorage("Interview storage capacity reached")
            if row:
                connection.execute(
                    "UPDATE workspace_usage SET reserved_bytes = reserved_bytes + ?, updated_at = ?"
                    " WHERE workspace = ?", (wanted, _now(), reserved_key))
            else:
                connection.execute(
                    "INSERT INTO workspace_usage (workspace, total_bytes, file_count, reserved_bytes,"
                    " updated_at) VALUES (?, 0, 0, ?, ?)", (reserved_key, wanted, _now()))
            connection.execute(
                "UPDATE global_usage SET reserved_bytes = reserved_bytes + ? WHERE id = 1", (wanted,))
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
    return wanted


def release(root: Path, key: str, *, reserved_bytes: int) -> None:
    """Drop a reservation that produced no retained bytes."""
    reserved = max(0, int(reserved_bytes))
    if not reserved:
        return
    _settle_reservation(root, str(key), reserved)


def write(
    root: Path,
    entry: str,
    *,
    total_bytes: int,
    file_count: int = 0,
    settle_reservation: int = 0,
) -> None:
    """Record one entry's measured size and optionally settle its reservation.

    The single writer of retained bytes: the global total moves by the change in
    this entry's own measurement, so a byte is counted once no matter which write
    path produced it, a shrink is honoured, and the reservation is released in the
    same transaction (no window where a written byte is uncounted).
    """
    name = str(entry)
    measured = max(0, int(total_bytes))
    files = max(0, int(file_count))
    settle = max(0, int(settle_reservation))
    with _thread_lock, _connect(root) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                "SELECT total_bytes FROM workspace_usage WHERE workspace = ?", (name,)
            ).fetchone()
            previous = int(row[0]) if row else 0
            if row:
                connection.execute(
                    "UPDATE workspace_usage SET total_bytes = ?, file_count = ?, updated_at = ?"
                    " WHERE workspace = ?", (measured, files, _now(), name))
            else:
                connection.execute(
                    "INSERT INTO workspace_usage (workspace, total_bytes, file_count, reserved_bytes,"
                    " updated_at) VALUES (?, ?, ?, 0, ?)", (name, measured, files, _now()))
            connection.execute(
                "UPDATE global_usage SET total_bytes = MAX(0, total_bytes + ?),"
                " reserved_bytes = MAX(0, reserved_bytes - ?) WHERE id = 1",
                (measured - previous, settle))
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise


def _settle_reservation(root: Path, key: str, reserved: int) -> None:
    if not reserved:
        return
    with _thread_lock, _connect(root) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            connection.execute(
                "UPDATE workspace_usage SET reserved_bytes = MAX(0, reserved_bytes - ?),"
                " updated_at = ? WHERE workspace = ?", (reserved, _now(), str(key)))
            connection.execute(
                "UPDATE global_usage SET reserved_bytes = MAX(0, reserved_bytes - ?) WHERE id = 1",
                (reserved,))
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise


def forget(root: Path, key: str) -> None:
    """Remove an entry and subtract its bytes (and any reservation) from the totals."""
    entry = str(key)
    with _thread_lock, _connect(root) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            row = connection.execute(
                "SELECT total_bytes, reserved_bytes FROM workspace_usage WHERE workspace = ?", (entry,)
            ).fetchone()
            if row:
                connection.execute("DELETE FROM workspace_usage WHERE workspace = ?", (entry,))
                connection.execute(
                    "UPDATE global_usage SET total_bytes = MAX(0, total_bytes - ?),"
                    " reserved_bytes = MAX(0, reserved_bytes - ?) WHERE id = 1",
                    (int(row[0]), int(row[1])))
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise


def reconcile(root: Path, measured: dict[str, tuple[int, int]]) -> StorageSnapshot:
    """Rebuild the ledger from a filesystem measurement (the authoritative source).

    Outstanding reservations are preserved so a concurrent writer is never
    over-admitted.
    """
    with _thread_lock, _connect(root) as connection:
        connection.execute("BEGIN IMMEDIATE")
        try:
            reservations = {
                str(row[0]): int(row[1])
                for row in connection.execute(
                    "SELECT workspace, reserved_bytes FROM workspace_usage WHERE reserved_bytes > 0")
            }
            connection.execute("DELETE FROM workspace_usage")
            retained = 0
            for name, (size, files) in measured.items():
                entry = str(name)
                reserved = reservations.pop(entry, 0)
                bytes_ = max(0, int(size))
                retained += bytes_
                connection.execute(
                    "INSERT INTO workspace_usage (workspace, total_bytes, file_count, reserved_bytes,"
                    " updated_at) VALUES (?, ?, ?, ?, ?)",
                    (entry, bytes_, max(0, int(files)), reserved, _now()))
            for entry, reserved in reservations.items():
                connection.execute(
                    "INSERT INTO workspace_usage (workspace, total_bytes, file_count, reserved_bytes,"
                    " updated_at) VALUES (?, 0, 0, ?, ?)", (entry, reserved, _now()))
            reserved_total = connection.execute(
                "SELECT COALESCE(SUM(reserved_bytes), 0) FROM workspace_usage").fetchone()[0]
            connection.execute(
                "UPDATE global_usage SET total_bytes = ?, reserved_bytes = ? WHERE id = 1",
                (retained, int(reserved_total or 0)))
            connection.execute("COMMIT")
        except BaseException:
            connection.execute("ROLLBACK")
            raise
    return snapshot(root)


def measure(root: Path) -> dict[str, tuple[int, int]]:
    """Walk the artifact root once and return per-entry ``(bytes, files)``.

    Reconciliation and metrics path, not a per-request path. Symlinks are never
    followed, so measurement cannot escape the artifact root.
    """
    measured: dict[str, tuple[int, int]] = {}
    if not root.is_dir():
        return measured
    ledger_file = _ledger_path(root)
    for name in os.listdir(root):
        entry = root / name
        if entry.is_symlink() or not entry.is_dir():
            continue
        total = 0
        count = 0
        for directory, dirs, files in os.walk(entry, followlinks=False):
            dirs[:] = [d for d in dirs if not (Path(directory) / d).is_symlink()]
            for filename in files:
                path = Path(directory) / filename
                if path.is_symlink() or path == ledger_file:
                    continue
                try:
                    total += path.stat().st_size
                except OSError:
                    continue
                count += 1
        measured[name] = (total, count)
    return measured


def _now() -> float:
    return time.time()

