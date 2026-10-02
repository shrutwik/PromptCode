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
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

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
            InterviewSession.status.in_(("created", "active"))
        )
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
        ws = Path(session.workspace_path) if session.workspace_path else workspace_root() / sid
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
                if base in known or name in protected_ids:
                    continue
                # Orphan: directory not tied to any session id
                try:
                    UUID(base)
                except ValueError:
                    continue
                _safe_rmtree(child, report, kind="orphan")

    if cleanup_docker:
        report.containers_removed = cleanup_promptcode_containers()

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
                if c.status in {"exited", "dead", "created"}:
                    c.remove(force=True)
                    removed += 1
            except Exception:  # noqa: BLE001
                logger.warning("Failed to remove container %s", getattr(c, "name", "?"))
    except Exception:  # noqa: BLE001
        logger.warning("Docker cleanup skipped (daemon unavailable)")
    return removed
