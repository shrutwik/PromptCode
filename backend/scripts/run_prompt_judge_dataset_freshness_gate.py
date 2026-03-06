"""Run prompt-judge sample freshness gate.

Usage:
    cd backend && python -m scripts.run_prompt_judge_dataset_freshness_gate
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any


def _parse_reviewed_at(raw: Any) -> datetime | None:
    text = str(raw or "").strip()
    if not text:
        return None
    try:
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def run_gate(
    *,
    samples_path: Path,
    min_total: int,
    min_recent: int,
    recent_days: int,
    min_unique_challenges: int,
    require_reviewed_at: bool,
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for line in samples_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, int(recent_days)))
    reviewed_missing = 0
    parse_failures = 0
    recent_count = 0
    challenges: set[str] = set()

    for row in rows:
        challenges.add(str(row.get("challenge_description") or "").strip().lower())
        reviewed_raw = (
            row.get("reviewed_at")
            or row.get("human_reviewed_at")
            or row.get("labeled_at")
            or ""
        )
        reviewed_at = _parse_reviewed_at(reviewed_raw)
        if not str(reviewed_raw).strip():
            reviewed_missing += 1
            continue
        if reviewed_at is None:
            parse_failures += 1
            continue
        if reviewed_at >= cutoff:
            recent_count += 1

    # Backward-compatible fallback: if metadata is missing but file itself is freshly
    # updated, treat the dataset as refreshed for non-strict mode.
    if not require_reviewed_at and recent_count == 0:
        try:
            mtime = datetime.fromtimestamp(samples_path.stat().st_mtime, tz=timezone.utc)
            if mtime >= cutoff:
                recent_count = len(rows)
        except Exception:
            pass

    checks = {
        "min_total": len(rows) >= min_total,
        "min_recent": recent_count >= min_recent,
        "min_unique_challenges": len({c for c in challenges if c}) >= min_unique_challenges,
        "reviewed_at_present": (reviewed_missing == 0 and parse_failures == 0) if require_reviewed_at else True,
    }
    passed = all(checks.values())

    return {
        "pass": passed,
        "sample_count": len(rows),
        "recent_count": recent_count,
        "recent_days": recent_days,
        "min_total": min_total,
        "min_recent": min_recent,
        "unique_challenge_count": len({c for c in challenges if c}),
        "min_unique_challenges": min_unique_challenges,
        "reviewed_at_missing": reviewed_missing,
        "reviewed_at_parse_failures": parse_failures,
        "require_reviewed_at": require_reviewed_at,
        "checks": checks,
        "method": "prompt_judge_dataset_freshness_v1",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run prompt-judge dataset freshness gate")
    parser.add_argument(
        "--samples",
        default=str(Path(__file__).resolve().parents[2] / "docs" / "prompt_judge_samples.jsonl"),
        help="Path to JSONL calibration samples",
    )
    parser.add_argument("--min-total", type=int, default=24)
    parser.add_argument("--min-recent", type=int, default=6)
    parser.add_argument("--recent-days", type=int, default=14)
    parser.add_argument("--min-unique-challenges", type=int, default=5)
    parser.add_argument(
        "--require-reviewed-at",
        action="store_true",
        help="Require every sample to include parseable reviewed_at metadata.",
    )
    args = parser.parse_args()

    result = run_gate(
        samples_path=Path(args.samples),
        min_total=args.min_total,
        min_recent=args.min_recent,
        recent_days=args.recent_days,
        min_unique_challenges=args.min_unique_challenges,
        require_reviewed_at=args.require_reviewed_at,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
