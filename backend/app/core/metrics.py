from __future__ import annotations

import asyncio
import os
import shutil
from datetime import datetime, timezone

from prometheus_client import REGISTRY, CollectorRegistry, Counter, Histogram

# Module-level singletons — registered once in the global Prometheus registry.

http_requests_total = Counter(
    "http_requests_total",
    "Total HTTP requests by method, path template, and status code.",
    ["method", "path", "status_code"],
)

http_request_duration_seconds = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds by method and path template.",
    ["method", "path"],
    buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0],
)


def get_metrics_registry() -> CollectorRegistry:
    """Return the correct Prometheus registry for the current process mode.

    Single-process (default): returns the global REGISTRY — standard counters work.
    Multi-process (uvicorn --workers N): set PROMETHEUS_MULTIPROC_DIR to a shared
    writable directory; this builds a per-scrape merged registry via MultiProcessCollector.
    """
    multiproc_dir = os.environ.get("PROMETHEUS_MULTIPROC_DIR", "").strip()
    if multiproc_dir:
        from prometheus_client.multiprocess import MultiProcessCollector

        registry = CollectorRegistry()
        MultiProcessCollector(registry)  # type: ignore[no-untyped-call]
        return registry
    return REGISTRY


async def operational_metrics(engine) -> bytes:
    """Read durable job state per scrape; never export candidate data or errors."""
    from prometheus_client import Gauge, generate_latest
    from sqlalchemy import func, select

    from app.models.interview_grading import InterviewGradingJob
    from app.services.interview.workspace import workspace_root
    registry = CollectorRegistry()
    jobs = Gauge('promptcode_grading_jobs', 'Persisted grading jobs by status.', ['status'], registry=registry)
    oldest = Gauge('promptcode_grading_oldest_queued_seconds', 'Age of oldest pending grading job.', registry=registry)
    stale = Gauge('promptcode_grading_stale_leases', 'Running grading jobs whose lease expired.', registry=registry)
    now = datetime.now(timezone.utc)
    async with engine.connect() as connection:
        counts = (await connection.execute(select(InterviewGradingJob.status, func.count())
                                          .group_by(InterviewGradingJob.status))).all()
        first = (await connection.execute(select(func.min(InterviewGradingJob.created_at))
                                         .where(InterviewGradingJob.status == 'queued'))).scalar_one()
        expired = (await connection.execute(select(func.count()).select_from(InterviewGradingJob)
            .where(InterviewGradingJob.status == 'running', InterviewGradingJob.lease_expires_at <= now))).scalar_one()
    count_map = dict(counts)
    for state in ('queued', 'running', 'completed', 'failed'):
        jobs.labels(state).set(count_map.get(state, 0))
    if first is not None and first.tzinfo is None:
        first = first.replace(tzinfo=timezone.utc)
    oldest.set(max(0, (now - first).total_seconds()) if first else 0)
    stale.set(expired)
    root = workspace_root()
    # Read the incremental ledger instead of walking the whole artifact tree on
    # every scrape; the scheduled reconciliation keeps it honest.
    from app.services.interview.workspace_quota import ledger_total
    Gauge('promptcode_interview_storage_bytes', 'Bytes of retained interview artifacts.', registry=registry).set(await asyncio.to_thread(ledger_total, root))
    Gauge('promptcode_interview_storage_free_bytes', 'Free bytes on interview artifact filesystem.', registry=registry).set(shutil.disk_usage(root).free)
    return generate_latest(registry)
