from __future__ import annotations

from prometheus_client import Counter, Histogram

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
