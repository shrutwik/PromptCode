"""Refit AI weight profile from historical submission outcomes.

Usage:
    cd backend && python -m scripts.refit_ai_weight_profile --dry-run
    cd backend && python -m scripts.refit_ai_weight_profile --output benchmarks/ai_weight_profile.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.submission import Submission
from app.services.evaluation.weight_profile import DEFAULT_PROFILE


def _safe_float(value: Any) -> float | None:
    try:
        if value is None:
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _corr(rows: list[dict[str, float]], feature: str, target: str = "target") -> float:
    xs: list[float] = []
    ys: list[float] = []
    for row in rows:
        x = row.get(feature)
        y = row.get(target)
        if x is None or y is None:
            continue
        xs.append(float(x))
        ys.append(float(y))

    n = len(xs)
    if n < 8:
        return 0.0

    mx = sum(xs) / n
    my = sum(ys) / n
    vx = sum((x - mx) ** 2 for x in xs) / n
    vy = sum((y - my) ** 2 for y in ys) / n
    if vx <= 0.0 or vy <= 0.0:
        return 0.0

    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=False)) / n
    return cov / ((vx**0.5) * (vy**0.5))


def _normalize_weights(raw: dict[str, float], *, defaults: dict[str, float], floor: float = 0.05) -> dict[str, float]:
    non_negative = {k: max(0.0, float(raw.get(k, 0.0))) for k in defaults.keys()}
    total = sum(non_negative.values())
    if total <= 1e-9:
        return dict(defaults)

    keys = list(defaults.keys())
    if floor * len(keys) >= 1.0:
        floor = 0.0
    spread = 1.0 - (floor * len(keys))

    normalized = {
        k: floor + (non_negative[k] / total) * spread
        for k in keys
    }
    final_total = sum(normalized.values())
    return {k: round(normalized[k] / final_total, 6) for k in keys}


def _derive_weights(
    rows: list[dict[str, float]],
    *,
    defaults: dict[str, float],
    min_rows: int,
) -> tuple[dict[str, float], dict[str, float]]:
    if len(rows) < min_rows:
        return dict(defaults), {k: 0.0 for k in defaults.keys()}

    correlations = {
        k: max(0.0, _corr(rows, k))
        for k in defaults.keys()
    }
    weights = _normalize_weights(correlations, defaults=defaults)
    return weights, {k: round(v, 4) for k, v in correlations.items()}


def _extract_rows(
    submissions: list[Submission],
    *,
    min_delta: float,
) -> tuple[list[dict[str, float]], list[dict[str, float]], list[dict[str, float]]]:
    grouped: dict[tuple[str, str], list[Submission]] = defaultdict(list)
    for sub in submissions:
        grouped[(str(sub.user_id), str(sub.challenge_id))].append(sub)

    with_baseline_rows: list[dict[str, float]] = []
    without_baseline_rows: list[dict[str, float]] = []
    future_rows: list[dict[str, float]] = []

    for seq in grouped.values():
        seq.sort(key=lambda s: ((s.completed_at or s.created_at), s.created_at))
        if len(seq) < 2:
            continue

        for i in range(len(seq) - 1):
            cur = seq[i]
            nxt = seq[i + 1]
            cur_overall = _safe_float(cur.score_overall)
            nxt_overall = _safe_float(nxt.score_overall)
            if cur_overall is None or nxt_overall is None:
                continue

            target = 1.0 if (nxt_overall - cur_overall) >= min_delta else 0.0
            report = cur.report if isinstance(cur.report, dict) else {}
            ai = report.get("ai_leverage") if isinstance(report.get("ai_leverage"), dict) else {}

            base_row = {
                "frontier_navigation": _safe_float(ai.get("frontier_navigation_score")),
                "reliance_calibration": _safe_float(ai.get("reliance_calibration_score")),
                "prompt_quality": _safe_float(cur.score_prompt_quality),
                "learning_velocity": _safe_float(ai.get("learning_velocity_score")),
                "target": target,
            }
            if all(v is not None for k, v in base_row.items() if k != "target"):
                without_baseline_rows.append({k: float(v) for k, v in base_row.items() if v is not None})

            with_row = dict(base_row)
            with_row["leverage_gain"] = _safe_float(ai.get("leverage_gain_score"))
            if all(v is not None for k, v in with_row.items() if k != "target"):
                with_baseline_rows.append({k: float(v) for k, v in with_row.items() if v is not None})

            future = report.get("future_feedback") if isinstance(report.get("future_feedback"), dict) else {}
            behavior = future.get("behavior_scores") if isinstance(future.get("behavior_scores"), dict) else {}
            future_row = {
                "verification_discipline": _safe_float(behavior.get("verification_discipline")),
                "efficient_leverage": _safe_float(behavior.get("efficient_leverage")),
                "adaptation_speed": _safe_float(behavior.get("adaptation_speed")),
                "evaluation_rigor": _safe_float(behavior.get("evaluation_rigor")),
                "target": target,
            }
            if all(v is not None for k, v in future_row.items() if k != "target"):
                future_rows.append({k: float(v) for k, v in future_row.items() if v is not None})

    return with_baseline_rows, without_baseline_rows, future_rows


async def build_profile(*, min_delta: float, min_rows: int) -> dict[str, Any]:
    async with async_session_factory() as db:
        result = await db.execute(
            select(Submission)
            .where(
                Submission.status == "completed",
                Submission.report.is_not(None),
            )
        )
        submissions = list(result.scalars().all())

    with_rows, without_rows, future_rows = _extract_rows(submissions, min_delta=min_delta)

    with_weights, with_corr = _derive_weights(
        with_rows,
        defaults=DEFAULT_PROFILE["ai_mastery_with_baseline"],
        min_rows=min_rows,
    )
    without_weights, without_corr = _derive_weights(
        without_rows,
        defaults=DEFAULT_PROFILE["ai_mastery_without_baseline"],
        min_rows=min_rows,
    )
    future_weights, future_corr = _derive_weights(
        future_rows,
        defaults=DEFAULT_PROFILE["future_readiness"],
        min_rows=min_rows,
    )

    return {
        "version": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "method": "outcome_correlation_v1",
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "sample_counts": {
            "ai_mastery_with_baseline": len(with_rows),
            "ai_mastery_without_baseline": len(without_rows),
            "future_readiness": len(future_rows),
        },
        "correlations": {
            "ai_mastery_with_baseline": with_corr,
            "ai_mastery_without_baseline": without_corr,
            "future_readiness": future_corr,
        },
        "ai_mastery_with_baseline": with_weights,
        "ai_mastery_without_baseline": without_weights,
        "future_readiness": future_weights,
    }


async def _run(args: argparse.Namespace) -> int:
    profile = await build_profile(min_delta=args.min_delta, min_rows=args.min_rows)
    text = json.dumps(profile, indent=2)

    if args.dry_run:
        print(text)
        return 0

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(text + "\n", encoding="utf-8")
    print(f"Saved profile to {output}")
    print(json.dumps(profile.get("sample_counts", {}), indent=2))
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(description="Refit AI mastery/readiness weight profile")
    parser.add_argument(
        "--output",
        default=str(Path(__file__).resolve().parents[1] / "benchmarks" / "ai_weight_profile.json"),
        help="Output path for generated weight profile JSON",
    )
    parser.add_argument(
        "--min-delta",
        type=float,
        default=0.02,
        help="Minimum next-attempt overall improvement considered successful",
    )
    parser.add_argument(
        "--min-rows",
        type=int,
        default=30,
        help="Minimum sample rows required before replacing defaults",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    import asyncio

    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
