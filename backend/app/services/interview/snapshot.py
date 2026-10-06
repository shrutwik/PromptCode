"""Bounded content-addressed submissions, outside candidate-visible workspaces."""
from __future__ import annotations

import fcntl
import hashlib
import json
import os
import shutil
import stat
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from app.services.interview.object_store import (
    ObjectStoreError,
    durable_submission_required,
    submission_prefix,
)
from app.services.interview.registry import is_blocked_path
from app.services.interview.workspace import (
    MAX_FILE_BYTES,
    SKIP_DIR_NAMES,
    workspace_root,
)
from app.services.interview.workspace_quota import (
    SOURCE_BYTES,
    SOURCE_FILES,
    storage_capacity,
)


@dataclass(frozen=True)
class FrozenSnapshot:
    """A verified local copy plus the provider-neutral key of the immutable source.

    ``source_path`` stays a real, digest-verified directory on this host so the
    existing Docker/filesystem consumers keep working; ``object_key`` names the
    same bytes in the durable object store (``submitted/<session>/<digest>``) and
    is what a durable grading job stores.
    """

    source_path: Path
    source_digest: str
    manifest: list[dict]
    object_key: str | None = None


def manifest_digest(manifest: list[dict]) -> str:
    return hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def _source_files(root: Path):
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Invalid source directory")
    for directory, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = sorted(d for d in dirs if d not in SKIP_DIR_NAMES)
        for name in dirs:
            if (Path(directory) / name).is_symlink():
                raise ValueError("Source links are not allowed")
        for name in sorted(files):
            path = Path(directory) / name
            rel = path.relative_to(root).as_posix()
            if is_blocked_path(rel):
                continue
            if path.is_symlink() or not stat.S_ISREG(path.stat().st_mode):
                raise ValueError("Source must contain regular files only")
            yield rel, path


def _contents(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd, "rb") as source:
        data = source.read(MAX_FILE_BYTES + 1)
    if len(data) > MAX_FILE_BYTES:
        raise ValueError("Submission file exceeds limit")
    return data


def _manifest(root: Path, target: Path | None = None) -> list[dict]:
    manifest = []
    total = 0
    for rel, path in _source_files(root):
        data = _contents(path)
        total += len(data)
        if total > SOURCE_BYTES or len(manifest) >= SOURCE_FILES:
            raise ValueError("Submission exceeds source quota")
        manifest.append({"path": rel, "sha256": hashlib.sha256(data).hexdigest(), "size": len(data)})
        if target is not None:
            dest = target / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            dest.chmod(0o444)
    return sorted(manifest, key=lambda item: item["path"])


def verify_snapshot(source_path: Path, source_digest: str) -> list[dict]:
    """Recompute bytes; a writable host cannot forge trust by editing a manifest."""
    source_path = Path(source_path)
    if (len(source_digest) != 64 or any(c not in "0123456789abcdef" for c in source_digest)
            or source_path.name != "source" or source_path.parent.name != source_digest):
        raise ValueError("Invalid snapshot identity")
    actual = _manifest(source_path)
    if not actual or manifest_digest(actual) != source_digest:
        raise ValueError("Submitted source integrity check failed")
    return actual


def _persist_managed_submission(session_id: str, digest: str, manifest: list[dict],
                                source_path: Path) -> None:
    """Mirror a frozen submission into the durable object store.

    Filesystem/local development keeps its existing byte-for-byte behavior. In
    managed storage and on Modal the container disk is only a cache, so the
    immutable objects must reach the store before the job is queued; the manifest
    object is written last and is the commit marker.
    """
    if not durable_submission_required():
        return
    from app.services.interview.workspace_store import persist_submission

    try:
        persist_submission(session_id, digest, manifest, source_path)
    except ObjectStoreError as exc:
        # The route maps ValueError to a retryable conflict; an infrastructure
        # failure must not leave a job queued against source the worker cannot fetch.
        raise ValueError("Submitted source could not be persisted to durable storage") from exc


def _frozen(session_id: str, source_path: Path, digest: str, manifest: list[dict]) -> FrozenSnapshot:
    return FrozenSnapshot(source_path, digest, manifest,
                          submission_prefix(session_id, digest))


def freeze_submission(workspace: Path, session_id: str) -> FrozenSnapshot:
    """Serialize against writes and reuse an already frozen submission on retry."""
    session_id = str(uuid.UUID(str(session_id)))
    workspace = Path(workspace)
    root = workspace_root().resolve()
    if workspace.is_symlink() or workspace.resolve() != root / session_id:
        raise ValueError("Invalid owned workspace")
    marker = Path(str(workspace) + ".submitted")
    with Path(str(workspace) + ".upload.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        destination_root = root / ".submitted" / session_id
        if marker.exists():
            digest = marker.read_text().strip()
            source_path = destination_root / digest / "source"
            manifest = verify_snapshot(source_path, digest)
            # The local marker is cache: re-assert the durable objects so a submit
            # that failed mid-upload can complete on retry.
            _persist_managed_submission(session_id, digest, manifest, source_path)
            return _frozen(session_id, source_path, digest, manifest)
        manifest = _manifest(workspace)
        if not manifest:
            raise ValueError("Submission is empty")
        required = sum(item['size'] for item in manifest) + len(json.dumps(manifest, sort_keys=True).encode()) + 64
        from app.services.interview.workspace_quota import measure_workspace
        with storage_capacity(required) as reserve_capacity:
            destination_root.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix="freeze-", dir=destination_root))
            try:
                source = temporary / "source"
                source.mkdir()
                copied = _manifest(workspace, source)
                if copied != manifest:
                    raise ValueError("Submission changed while freezing")
                digest = manifest_digest(manifest)
                (temporary / "manifest.json").write_text(json.dumps(manifest, sort_keys=True))
                (temporary / "manifest.json").chmod(0o444)
                for directory, _, _ in os.walk(source, topdown=False):
                    Path(directory).chmod(0o555)
                destination = destination_root / digest
                reused = destination.exists()
                if reused:
                    verify_snapshot(destination / "source", digest)
                else:
                    temporary.rename(destination)
                marker.write_text(digest)
                _persist_managed_submission(session_id, digest, manifest, destination / "source")
            finally:
                if temporary.exists():
                    for directory, _, _ in os.walk(temporary):
                        Path(directory).chmod(0o755)
                    shutil.rmtree(temporary)
            # Record the immutable snapshot under its own key and settle the
            # admission in the same transaction. A reused digest adds nothing
            # because the entry's measurement is unchanged.
            total, files = measure_workspace(destination_root / digest)
            reserve_capacity(digest, total, files)
        return _frozen(session_id, destination_root / digest / "source", digest, manifest)
