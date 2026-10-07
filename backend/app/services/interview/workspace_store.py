"""Ephemeral-container workspace hydration and durable submission storage.

Two separate problems, both caused by ephemeral containers:

* ``interview_sessions.workspace_path`` is a container-local directory that does
  not exist on the next request. :func:`ensure_workspace` rebuilds it on demand:
  the immutable starter tree comes from the challenge source and saved progress
  comes from the latest revision per path in ``interview_session_files`` (the
  source of truth for candidate edits, append-only). On the filesystem backend an
  existing directory is returned untouched, so local behavior is unchanged.
* A frozen submission must survive container loss and stay verifiable by digest at
  grading time. :func:`persist_submission` writes the immutable objects to the
  object store (``submitted/{session_id}/{source_digest}/{rel_path}``) with the
  manifest LAST as the commit marker, and :func:`fetch_submission` re-verifies
  every byte before the evaluator sees it.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import tempfile
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import and_, func, select

from app.models.interview_session import InterviewSessionFile
from app.services.interview.object_store import (
    ObjectNotFound,
    get_object_store,
    manifest_key,
    normalize_rel_path,
    submission_key,
    submission_prefix,
)
from app.services.interview.registry import is_blocked_path


async def ensure_workspace(db, session) -> Path:
    """Return a workspace that exists on this container, rebuilding it if lost.

    A directory that already exists is a no-op. Otherwise the starter tree is
    recreated from the challenge source and the latest saved revision of every
    path is overlaid, so any container can serve the next request. The session's
    ``workspace_path`` is repointed when the container root differs.
    """
    from app.services.interview.workspace import create_workspace, workspace_root

    recorded = str(getattr(session, "workspace_path", "") or "")
    if recorded and _materialized(Path(recorded)):
        return Path(recorded)
    target = workspace_root() / str(session.id)
    if not _materialized(target):
        target = await asyncio.to_thread(create_workspace, str(session.id), session.challenge_slug)
    revisions = await _latest_revisions(db, session.id)
    if revisions:
        await asyncio.to_thread(_overlay_revisions, target, revisions)
    if str(target) != recorded:
        session.workspace_path = str(target)
        await db.flush()
    return target


def _materialized(workspace: Path) -> bool:
    try:
        return workspace.is_dir() and any(workspace.iterdir())
    except OSError:
        return False


async def _latest_revisions(db, session_id) -> list[tuple[str, str]]:
    """Latest revision per path, the append-only source of truth for edits."""
    latest = (
        select(InterviewSessionFile.path, func.max(InterviewSessionFile.revision).label("revision"))
        .where(InterviewSessionFile.session_id == session_id)
        .group_by(InterviewSessionFile.path)
        .subquery()
    )
    rows = (await db.execute(
        select(InterviewSessionFile.path, InterviewSessionFile.content)
        .join(latest, and_(InterviewSessionFile.path == latest.c.path,
                           InterviewSessionFile.revision == latest.c.revision))
        .where(InterviewSessionFile.session_id == session_id)
    )).all()
    return [(str(path), content or "") for path, content in rows]


def _overlay_revisions(workspace: Path, revisions) -> int:
    """Replay saved edits into a rebuilt workspace, skipping forbidden paths."""
    from app.services.interview.workspace import candidate_write_allowed, contained_file

    written = 0
    for rel_path, content in revisions:
        # The same policy that guards a live save: never replay a blocked or
        # frozen path (tests, private files) from storage.
        if is_blocked_path(rel_path) or not candidate_write_allowed(workspace, rel_path):
            continue
        target = contained_file(workspace, rel_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
        written += 1
    return written


def _sorted_manifest(manifest) -> list[dict]:
    rows = [dict(row) for row in (manifest or [])]
    for row in rows:
        if not {"path", "sha256", "size"} <= set(row):
            raise ValueError("Invalid submission manifest")
    if not rows:
        raise ValueError("Submission manifest is empty")
    return sorted(rows, key=lambda item: item["path"])


def _manifest_digest(manifest: list[dict]) -> str:
    from app.services.interview.snapshot import manifest_digest

    return manifest_digest(manifest)


def _verified(store, session_id: str, source_digest: str, manifest: list[dict]) -> bool:
    """Recompute every stored object against the manifest it is named by."""
    for item in manifest:
        try:
            data = store.get(submission_key(session_id, source_digest, item["path"]))
        except ObjectNotFound:
            return False
        if len(data) != int(item["size"]) or hashlib.sha256(data).hexdigest() != item["sha256"]:
            return False
    return True


def _committed_manifest(store, session_id: str, source_digest: str) -> list[dict] | None:
    """Read and verify the stored commit marker, or ``None`` when absent."""
    try:
        raw = store.get(manifest_key(session_id, source_digest))
    except ObjectNotFound:
        return None
    try:
        manifest = _sorted_manifest(json.loads(raw.decode("utf-8")))
    except (ValueError, UnicodeDecodeError):
        return None
    return manifest if _manifest_digest(manifest) == source_digest else None


def persist_submission(session_id, source_digest, manifest, src_dir) -> str:
    """Persist an immutable, content-addressed submission and return its prefix.

    Idempotent: a repeated digest whose stored bytes still verify is a no-op.
    Objects are uploaded first and ``manifest.json`` last, so the manifest is the
    commit marker and an interrupted upload is invisible to readers.
    """
    store = get_object_store()
    session_id, source_digest = str(session_id), str(source_digest)
    rows = _sorted_manifest(manifest)
    if _manifest_digest(rows) != source_digest:
        raise ValueError("Submission digest does not match its manifest")
    if _committed_manifest(store, session_id, source_digest) is not None \
            and _verified(store, session_id, source_digest, rows):
        return submission_prefix(session_id, source_digest)
    source = Path(src_dir)
    for item in rows:
        rel = normalize_rel_path(item["path"])
        data = (source / rel).read_bytes()
        if len(data) != int(item["size"]) or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Submission changed while persisting")
        key = submission_key(session_id, source_digest, rel)
        try:
            if store.get(key) == data:
                continue
        except ObjectNotFound:
            pass
        store.put(key, data)
    store.put(manifest_key(session_id, source_digest),
              json.dumps(rows, sort_keys=True).encode("utf-8"))
    return submission_prefix(session_id, source_digest)


def fetch_submission(session_id, source_digest, manifest, dest_dir) -> Path:
    """Download, verify and materialize an immutable submission.

    The recomputed manifest must match ``source_digest`` and the written tree is
    re-verified with :func:`verify_snapshot`, so a tampered or half-written object
    can never reach the evaluator.
    """
    from app.services.interview.snapshot import verify_snapshot

    store = get_object_store()
    session_id, source_digest = str(session_id), str(source_digest)
    rows = _sorted_manifest(manifest) if manifest else _committed_manifest(store, session_id, source_digest)
    if rows is None:
        raise ValueError("Submission is not committed")
    if _manifest_digest(rows) != source_digest:
        raise ValueError("Submitted source integrity check failed")
    contents = []
    for item in rows:
        rel = normalize_rel_path(item["path"])
        try:
            data = store.get(submission_key(session_id, source_digest, rel))
        except ObjectNotFound:
            raise ValueError("Submitted source integrity check failed") from None
        if len(data) != int(item["size"]) or hashlib.sha256(data).hexdigest() != item["sha256"]:
            raise ValueError("Submitted source integrity check failed")
        contents.append((rel, data))
    source = Path(dest_dir) / source_digest / "source"
    for rel, data in contents:
        target = _contained(source, rel)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        target.chmod(0o444)
    verify_snapshot(source, source_digest)
    return source


@contextmanager
def verified_job_source(job, *, require_ownership: bool = True):
    """Yield a verified, readable copy of a grading job's immutable submission.

    Every reader of submitted work (grading, staff review, appeal, retry) must use
    this instead of ``job.snapshot_path``: on the managed stack the recorded host
    path does not exist in a fresh container, so reading it directly would fail
    closed with a 409. Identity is proven from the job row itself — the object key
    must be the one derived from this session and digest, and in durable mode every
    downloaded object is re-verified against the stored manifest.

    ``require_ownership`` keeps the strict host-path check used by the automated
    grading worker. The interactive review/retry readers historically verified the
    submission by digest only, so they pass ``False`` and keep that contract rather
    than gaining a new 409.
    """
    from app.services.interview.object_store import (
        durable_submission_required,
        submission_prefix,
    )

    session_id = str(job.session_id)
    digest = str(job.source_digest)
    expected_key = submission_prefix(session_id, digest)
    key = getattr(job, "snapshot_key", None)
    if key is not None and key != expected_key:
        raise ValueError("Invalid submitted source ownership")
    if durable_submission_required():
        manifest = (getattr(job, "snapshot_manifest", None) or {}).get("files") or []
        root = Path(tempfile.mkdtemp(prefix="grading-source-"))
        try:
            yield fetch_submission(session_id, digest, manifest, root)
        finally:
            shutil.rmtree(root, ignore_errors=True)
        return
    source = Path(job.snapshot_path)
    if require_ownership:
        from app.services.interview.workspace import workspace_root

        expected = workspace_root().resolve() / ".submitted" / session_id / digest / "source"
        if source.is_symlink() or source.resolve() != expected:
            raise ValueError("Invalid submitted source ownership")
    yield source


def _contained(root: Path, rel_path: str) -> Path:
    """Resolve ``rel_path`` inside ``root`` and refuse links or escapes."""
    rel = normalize_rel_path(rel_path)
    if is_blocked_path(rel):
        raise ValueError("Invalid object path")
    base = Path(root).resolve()
    resolved = (base / rel).resolve()
    if resolved != base and base not in resolved.parents:
        raise ValueError("Object path escapes its root")
    return resolved
