"""Incremental storage accounting and bounded execution admission.

These cover the two measured bottlenecks: per-request full-root scans under a
global lock, and instant shedding when every execution slot is busy.
"""
from __future__ import annotations

import asyncio

import pytest

from app.core.capacity_queue import CapacityExceeded, CapacityQueue, CapacityTimeout
from app.services.interview import storage_ledger as ledger
from app.services.interview import workspace_quota as quota


def test_ledger_tracks_bytes_and_files_across_reserve_and_write(tmp_path):
    reserved = ledger.reserve(tmp_path, "reservations", workspace_limit_bytes=0,
                              workspace_limit_files=0, global_limit_bytes=1000,
                              min_free_bytes=0, additional_bytes=40, additional_files=0)
    assert reserved == 40
    assert ledger.snapshot(tmp_path).reserved_bytes == 40
    # One atomic write records the measured entry and settles the reservation.
    ledger.write(tmp_path, "session-a", total_bytes=25, file_count=2, settle_reservation=reserved)
    assert ledger.workspace_usage(tmp_path, "session-a").bytes == 25
    assert ledger.workspace_usage(tmp_path, "session-a").files == 2
    assert ledger.snapshot(tmp_path).total_bytes == 25
    assert ledger.snapshot(tmp_path).reserved_bytes == 0


def test_ledger_rejects_over_commit_and_releases_reservation(tmp_path):
    with pytest.raises(ledger.InsufficientStorage):
        ledger.reserve(tmp_path, "s", workspace_limit_bytes=10, workspace_limit_files=10,
                       global_limit_bytes=1000, min_free_bytes=0,
                       additional_bytes=11, additional_files=0)
    assert ledger.snapshot(tmp_path).total_bytes == 0
    reserved = ledger.reserve(tmp_path, "s", workspace_limit_bytes=10, workspace_limit_files=10,
                              global_limit_bytes=1000, min_free_bytes=0,
                              additional_bytes=10, additional_files=1)
    assert ledger.snapshot(tmp_path).reserved_bytes == 10
    ledger.release(tmp_path, "s", reserved_bytes=reserved)
    assert ledger.snapshot(tmp_path).total_bytes == 0
    assert ledger.snapshot(tmp_path).reserved_bytes == 0


def test_ledger_enforces_the_global_bound_across_workspaces(tmp_path):
    ledger.write(tmp_path, "one", total_bytes=8, file_count=1)
    with pytest.raises(ledger.InsufficientStorage):
        ledger.reserve(tmp_path, "two", workspace_limit_bytes=0, workspace_limit_files=0,
                       global_limit_bytes=10, min_free_bytes=0,
                       additional_bytes=3, additional_files=1)


def test_reconcile_rebuilds_the_ledger_from_the_filesystem(tmp_path):
    workspace = tmp_path / "session-z"
    workspace.mkdir()
    (workspace / "a.py").write_bytes(b"x" * 7)
    # Simulate drift: the ledger over-reports before reconciliation.
    ledger.write(tmp_path, "session-z", total_bytes=999, file_count=99)
    snapshot = ledger.reconcile(tmp_path, ledger.measure(tmp_path))
    assert snapshot.total_bytes == 7
    assert ledger.workspace_usage(tmp_path, "session-z").files == 1


def test_storage_capacity_denial_is_fail_closed_with_retry_hint(tmp_path, monkeypatch):
    from fastapi import HTTPException

    monkeypatch.setenv("PROMPTCODE_INTERVIEW_WORKSPACE_ROOT", str(tmp_path))
    monkeypatch.setenv("PROMPTCODE_INTERVIEW_STORAGE_MAX_BYTES", "10")
    monkeypatch.setenv("PROMPTCODE_INTERVIEW_STORAGE_MIN_FREE_BYTES", "0")
    from app.core.config import get_settings
    get_settings.cache_clear()
    try:
        with quota.storage_capacity(8) as reserve:
            reserve("session-a", 8, 1)
        with pytest.raises(HTTPException) as exc, quota.storage_capacity(8):
            pass
        assert exc.value.status_code == 507
        assert exc.value.headers.get("Retry-After")
    finally:
        get_settings.cache_clear()


def test_storage_capacity_releases_the_reservation_when_the_write_fails(tmp_path, monkeypatch):
    monkeypatch.setenv("PROMPTCODE_INTERVIEW_WORKSPACE_ROOT", str(tmp_path))
    from app.core.config import get_settings
    get_settings.cache_clear()
    try:
        with pytest.raises(RuntimeError), quota.storage_capacity(4096):
            raise RuntimeError("write failed")
        assert ledger.snapshot(tmp_path).reserved_bytes == 0
        assert ledger.snapshot(tmp_path).total_bytes == 0
    finally:
        get_settings.cache_clear()


def test_capacity_queue_admits_fifo_and_reports_waiting():
    async def exercise():
        queue = CapacityQueue(slots=1, max_waiters=4, deadline_seconds=1)
        first = asyncio.create_task(queue.acquire())
        await first
        order: list[int] = []

        async def waiter(index: int) -> None:
            await queue.acquire()
            order.append(index)

        tasks = [asyncio.create_task(waiter(i)) for i in range(3)]
        await asyncio.sleep(0.05)
        assert queue.stats().waiting == 3
        for _ in range(3):
            queue.release()
            await asyncio.sleep(0.05)
        await asyncio.gather(*tasks)
        assert order == [0, 1, 2]
        assert queue.stats().waiting == 0
    asyncio.run(exercise())


def test_capacity_queue_fails_closed_when_the_backlog_is_full():
    async def exercise():
        queue = CapacityQueue(slots=1, max_waiters=2, deadline_seconds=1)
        await queue.acquire()
        waiters = [asyncio.create_task(queue.acquire()) for _ in range(2)]
        await asyncio.sleep(0.05)
        with pytest.raises(CapacityExceeded):
            await queue.acquire()
        queue.release()
        queue.release()
        await asyncio.gather(*waiters)
    asyncio.run(exercise())


def test_capacity_queue_honours_the_wait_deadline():
    async def exercise():
        queue = CapacityQueue(slots=1, max_waiters=4, deadline_seconds=0.1)
        await queue.acquire()
        with pytest.raises(CapacityTimeout):
            await queue.acquire()
        assert queue.stats().waiting == 0
        queue.release()
    asyncio.run(exercise())


def test_ledger_reports_read_only_roles(tmp_path):
    """A grading worker mounts the artifact root read-only and must stand down."""
    assert ledger.is_writable(tmp_path) is True
    read_only = tmp_path / "ro"
    read_only.mkdir()
    read_only.chmod(0o500)
    try:
        assert ledger.is_writable(read_only) is False
    finally:
        read_only.chmod(0o700)


def test_reconcile_loop_stands_down_when_the_root_is_read_only(monkeypatch):
    """The worker loop returns promptly instead of warning every interval."""
    import asyncio

    from app.services.interview import storage_ledger
    from app.workers import queue as worker_queue

    monkeypatch.setattr(storage_ledger, "is_writable", lambda _root: False)
    asyncio.run(asyncio.wait_for(worker_queue._storage_ledger_reconcile_loop(), timeout=2))
