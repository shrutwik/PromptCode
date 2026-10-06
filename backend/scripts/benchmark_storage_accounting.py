"""Measure the per-save cost of capacity admission before and after the ledger.

Builds a disposable artifact tree at a representative size, then times:

* the previous implementation, ``retained_bytes(root)`` inside the host-wide
  ``.storage.lock`` (a full artifact-root walk per write), and
* the ledger path, ``storage_capacity`` admission plus the measured entry record.

Writes only under a temporary directory and touches no existing data. Run from
``backend/`` with the repository virtual environment:

    python -m scripts.benchmark_storage_accounting --sessions 200 --files 4
"""
from __future__ import annotations

import argparse
import fcntl
import os
import statistics
import tempfile
import time
from pathlib import Path

from app.core.config import get_settings
from app.services.interview import storage_ledger as ledger
from app.services.interview import workspace_quota as quota


def _build_tree(root: Path, sessions: int, files: int, payload: int) -> None:
    for index in range(sessions):
        workspace = root / f"00000000-0000-4000-8000-{index:012d}"
        workspace.mkdir(parents=True, exist_ok=True)
        for name in range(files):
            (workspace / f"file{name}.py").write_bytes(b"x" * payload)
        starter = root / f"{workspace.name}.starter"
        starter.mkdir(exist_ok=True)
        for name in range(files):
            (starter / f"file{name}.py").write_bytes(b"x" * payload)


def _time_full_scan(root: Path, rounds: int) -> list[float]:
    samples: list[float] = []
    with (root / ".storage.lock").open("a") as lock:
        for _ in range(rounds):
            start = time.perf_counter()
            fcntl.flock(lock, fcntl.LOCK_EX)
            quota.retained_bytes(root)
            fcntl.flock(lock, fcntl.LOCK_UN)
            samples.append(time.perf_counter() - start)
    return samples


def _time_ledger(root: Path, workspace: Path, rounds: int) -> list[float]:
    samples: list[float] = []
    for index in range(rounds):
        start = time.perf_counter()
        with quota.storage_capacity(1024) as reserve:
            (workspace / f"save{index}.py").write_bytes(b"y" * 512)
            total, files = quota.measure_workspace(workspace)
            reserve(workspace.name, total, files)
        samples.append(time.perf_counter() - start)
    return samples


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions", type=int, default=200)
    parser.add_argument("--files", type=int, default=4)
    parser.add_argument("--payload", type=int, default=4096)
    parser.add_argument("--rounds", type=int, default=30)
    args = parser.parse_args()

    with tempfile.TemporaryDirectory(prefix="promptcode-storage-bench-") as tmp:
        root = Path(tmp)
        os.environ["PROMPTCODE_INTERVIEW_WORKSPACE_ROOT"] = str(root)
        os.environ["PROMPTCODE_INTERVIEW_STORAGE_MIN_FREE_BYTES"] = "0"
        get_settings.cache_clear()
        _build_tree(root, args.sessions, args.files, args.payload)
        ledger.reconcile(root, ledger.measure(root))
        workspace = next(path for path in root.iterdir()
                         if path.is_dir() and not path.name.endswith(".starter"))
        full = _time_full_scan(root, args.rounds)
        incremental = _time_ledger(root, workspace, args.rounds)
        retained = ledger.total_bytes(root)
        print(f"sessions={args.sessions} files/session={args.files} payload={args.payload}B "
              f"retained={retained / 1024 / 1024:.2f} MiB")
        print(f"full-root scan under lock : p50={statistics.median(full) * 1000:.2f} ms "
              f"p95={sorted(full)[int(len(full) * 0.95) - 1] * 1000:.2f} ms")
        print(f"ledger admission + record : p50={statistics.median(incremental) * 1000:.2f} ms "
              f"p95={sorted(incremental)[int(len(incremental) * 0.95) - 1] * 1000:.2f} ms")
        speedup = statistics.median(full) / max(statistics.median(incremental), 1e-9)
        print(f"median speedup: {speedup:.1f}x")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
