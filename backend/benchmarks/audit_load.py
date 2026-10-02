"""Short local load probe for the audit.

Hits a server already running on 127.0.0.1:8000. Does not create users.
Prints status counts and latency percentiles. Stop if error rates climb.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "http://127.0.0.1:8000"


def percentile(samples: list[float], pct: float) -> float | None:
    if not samples:
        return None
    ordered = sorted(samples)
    index = min(len(ordered) - 1, max(0, int(round((pct / 100) * (len(ordered) - 1)))))
    return round(ordered[index], 2)


def hit(path: str, method: str = "GET", data: bytes | None = None, headers: dict | None = None) -> tuple[int, float]:
    request = urllib.request.Request(BASE + path, data=data, headers=headers or {}, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=8) as response:
            response.read()
            code = response.status
    except urllib.error.HTTPError as exc:
        exc.read()
        code = exc.code
    except Exception:
        code = 0
    return code, (time.perf_counter() - started) * 1000


def load(path: str, workers: int, per_worker: int) -> None:
    total = workers * per_worker
    with ThreadPoolExecutor(max_workers=workers) as pool:
        results = list(pool.map(lambda _: hit(path), range(total)))
    latencies = [ms for code, ms in results if code == 200]
    errors: dict[int, int] = {}
    for code, _ms in results:
        errors[code] = errors.get(code, 0) + 1
    print(
        f"{path} concurrency={workers} n={total} statuses={errors} "
        f"p50={percentile(latencies, 50)} p95={percentile(latencies, 95)} "
        f"p99={percentile(latencies, 99)}"
    )


def main() -> None:
    for workers in (1, 10, 25, 50):
        load("/health", workers, 10)
    for workers in (1, 10, 25):
        load("/api/interview/challenges", workers, 8)
    body = json.dumps(
        {"email": "nobody-audit@example.com", "password": "Wrong!Password1"}
    ).encode()
    headers = {"Content-Type": "application/json"}
    codes = [hit("/api/auth/login", "POST", body, headers)[0] for _ in range(15)]
    print("login burst", codes)


if __name__ == "__main__":
    main()
