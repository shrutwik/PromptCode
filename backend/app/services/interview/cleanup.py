"""Idempotent cleanup for expired/failed/orphan interview workspaces.

Never deletes:
- source challenges/
- active session workspaces
- submitted report DB artifacts
- other users' in-progress workspaces
"""

from __future__ import annotations

import logging
import shutil
import time
from dataclasses import dataclass, field
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.interview_grading import (
    InterviewGradeAppeal,
    InterviewGradeReview,
    InterviewGradingJob,
)
from app.models.interview_session import InterviewSession
from app.services.interview.lifecycle import maybe_expire_session, utcnow
from app.services.interview.workspace import starter_snapshot_path, workspace_root

logger = logging.getLogger(__name__)

PROMPTCODE_CONTAINER_LABEL = "promptcode.role=interview-runner"


@dataclass
class CleanupReport:
    expired_sessions: int = 0
    workspaces_removed: int = 0
    starters_removed: int = 0
    orphan_dirs_removed: int = 0
    containers_removed: int = 0
    errors: list[str] = field(default_factory=list)


def _safe_rmtree(path: Path, report: CleanupReport, *, kind: str) -> None:
    if not path.exists():
        return
    try:
        shutil.rmtree(path)
        # Retained-byte accounting is derived; forgetting the removed entry keeps
        # the storage cap honest without a rescan.
        from app.services.interview.workspace_quota import forget_workspace
        forget_workspace(path)
        if kind == "workspace":
            report.workspaces_removed += 1
        elif kind == "starter":
            report.starters_removed += 1
        else:
            report.orphan_dirs_removed += 1
    except OSError as exc:
        report.errors.append(f"{path}: {exc}")
        logger.warning("cleanup failed for %s: %s", path, exc)


async def expire_due_sessions(db: AsyncSession) -> int:
    result = await db.execute(
        select(InterviewSession).where(
            InterviewSession.status.in_(("created", "active")),
            InterviewSession.expires_at <= utcnow(),
        ).with_for_update(skip_locked=True).execution_options(populate_existing=True)
    )
    count = 0
    for session in result.scalars().all():
        if maybe_expire_session(session):
            count += 1
    if count:
        await db.commit()
    return count


async def cleanup_interview_resources(
    db: AsyncSession,
    *,
    remove_workspaces_for: tuple[str, ...] = ("expired", "failed"),
    sweep_orphans: bool = True,
    cleanup_docker: bool = True,
) -> CleanupReport:
    report = CleanupReport()
    report.expired_sessions = await expire_due_sessions(db)

    result = await db.execute(
        select(InterviewSession).where(InterviewSession.status.in_(remove_workspaces_for))
    )
    sessions = list(result.scalars().all())
    protected_ids: set[str] = set()
    # Source referenced by durable grading/review/appeal history must remain
    # available even when the session was subsequently marked failed/expired.
    for model in (InterviewGradingJob, InterviewGradeReview, InterviewGradeAppeal):
        retained = (await db.execute(select(model.session_id))).scalars().all()
        for sid in retained:
            protected_ids.update((str(sid), f'{sid}.starter'))

    # Protect active + submitted workspace dirs (history retained; only temp dirs for expired/failed)
    all_sessions = (
        await db.execute(select(InterviewSession.id, InterviewSession.status))
    ).all()
    for sid, status in all_sessions:
        sid_s = str(sid)
        if status in {"created", "active", "submitted"}:
            protected_ids.add(sid_s)
            protected_ids.add(f"{sid_s}.starter")

    for session in sessions:
        sid = str(session.id)
        if sid in protected_ids:
            continue
        ws = Path(session.workspace_path) if session.workspace_path else workspace_root() / sid
        if ws.is_symlink() or ws.resolve() != workspace_root().resolve() / sid:
            report.errors.append(f'Blocked workspace outside owned root: {sid}')
            continue
        _safe_rmtree(ws, report, kind="workspace")
        _safe_rmtree(starter_snapshot_path(sid), report, kind="starter")
        # Keep DB history; clear path pointer when workspace gone
        if not ws.exists():
            session.workspace_path = ""
    await db.commit()

    if sweep_orphans:
        root = workspace_root()
        if root.exists():
            known = {str(r[0]) for r in all_sessions}
            for child in root.iterdir():
                name = child.name
                base = name.removesuffix(".starter")
                if base in known or name in protected_ids or child.is_symlink():
                    continue
                # Creation precedes the session DB commit. Give newly created
                # directories a grace period rather than racing that transaction.
                if child.stat().st_mtime > time.time() - 3600:
                    continue
                # Orphan: directory not tied to any session id
                try:
                    UUID(base)
                except ValueError:
                    continue
                _safe_rmtree(child, report, kind="orphan")

    if cleanup_docker:
        report.containers_removed = cleanup_promptcode_containers()

    # Deletions above already decremented the ledger; reconcile from the
    # filesystem at the end of every sweep so drift cannot accumulate.
    try:
        import asyncio

        from app.services.interview.workspace_quota import refresh_ledger
        await asyncio.to_thread(refresh_ledger)
    except Exception:
        logger.warning("storage ledger reconciliation failed", exc_info=True)

    return report


def cleanup_promptcode_containers() -> int:
    """Remove stopped/dangling PromptCode interview runner containers."""
    removed = 0
    try:
        import docker
    except ImportError:
        return 0
    try:
        client = docker.from_env(timeout=10)
        containers = client.containers.list(
            all=True,
            filters={"label": "promptcode.role=interview-runner"},
        )
        for c in containers:
            try:
                # Only remove non-running leftovers (running ones are mid-test)
                if c.status in {"exited", "dead"}:
                    c.remove(force=True)
                    removed += 1
            except Exception:  # noqa: BLE001
                logger.warning("Failed to remove container %s", getattr(c, "name", "?"))
    except Exception:  # noqa: BLE001
        logger.warning("Docker cleanup skipped (daemon unavailable)")
    return removed
