"""Run prompt-judge calibration gate.

Usage:
    cd backend && python -m scripts.run_prompt_judge_calibration_gate
    cd backend && python -m scripts.run_prompt_judge_calibration_gate --mode heuristic --min-samples 20 --min-pearson 0.75 --max-mae 0.25
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from scripts.calibrate_prompt_judge import evaluate_sample, load_samples, pearson


def _normalize_prompts(prompts: list[dict]) -> list[dict]:
    normalized: list[dict] = []
    for p in prompts:
        normalized.append(
            {
                "system": str(p.get("system", "")),
                "user": str(p.get("user", "")),
                "model": str(p.get("model", "unknown")),
            }
        )
    return normalized


def run_gate(
    *,
    samples_path: Path,
    mode: str,
    min_samples: int,
    min_pearson: float,
    max_mae: float,
    require_judge_mode: bool,
) -> dict:
    if require_judge_mode and mode != "judge":
        return {
            "pass": False,
            "reason": "judge_mode_required",
            "mode": mode,
        }

    samples = load_samples(samples_path)
    if len(samples) < min_samples:
        return {
            "pass": False,
            "reason": "insufficient_samples",
            "sample_count": len(samples),
            "required_min_samples": min_samples,
        }

    human: list[float] = []
    model: list[float] = []
    for s in samples:
        prompts = _normalize_prompts(s.get("prompts", []))
        human_score = float(s["human_overall"])
        try:
            model_score = evaluate_sample(
                {
                    "prompts": prompts,
                    "challenge_description": s.get("challenge_description", ""),
                },
                mode,
            )
        except Exception as exc:
            return {
                "pass": False,
                "reason": "evaluation_error",
                "mode": mode,
                "error": str(exc),
            }
        human.append(human_score)
        model.append(model_score)

    mae = mean(abs(h - m) for h, m in zip(human, model)) if human else 0.0
    corr = pearson(human, model) if human else 0.0
    passed = corr >= min_pearson and mae <= max_mae

    return {
        "pass": passed,
        "mode": mode,
        "sample_count": len(samples),
        "pearson_r": round(corr, 4),
        "mae": round(mae, 4),
        "thresholds": {
            "min_pearson": min_pearson,
            "max_mae": max_mae,
            "min_samples": min_samples,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--samples",
        default=str(Path(__file__).resolve().parents[2] / "docs" / "prompt_judge_samples.jsonl"),
        help="Path to JSONL calibration samples",
    )
    parser.add_argument("--mode", choices=["judge", "heuristic"], default="heuristic")
    parser.add_argument("--min-samples", type=int, default=20)
    parser.add_argument("--min-pearson", type=float, default=0.75)
    parser.add_argument("--max-mae", type=float, default=0.25)
    parser.add_argument(
        "--require-judge-mode",
        action="store_true",
        help="Fail unless mode=judge (use for release-grade checks).",
    )
    args = parser.parse_args()

    result = run_gate(
        samples_path=Path(args.samples),
        mode=args.mode,
        min_samples=args.min_samples,
        min_pearson=args.min_pearson,
        max_mae=args.max_mae,
        require_judge_mode=args.require_judge_mode,
    )
    print(json.dumps(result, indent=2))
    if not result.get("pass", False):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
