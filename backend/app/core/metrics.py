from __future__ import annotations

import os

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
