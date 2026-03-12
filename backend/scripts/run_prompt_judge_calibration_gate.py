"""Run prompt-judge calibration gate.

Usage:
    cd backend && python -m scripts.run_prompt_judge_calibration_gate
    cd backend && python -m scripts.run_prompt_judge_calibration_gate --mode heuristic --min-samples 20 --min-pearson 0.75 --max-mae 0.25
"""

from __future__ import annotations

import argparse
import hashlib
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


def _default_lock_path(samples_path: Path) -> Path:
    return samples_path.with_name("prompt_judge_calibration.lock.json")


def _samples_sha256(samples_path: Path) -> str:
    return hashlib.sha256(samples_path.read_bytes()).hexdigest()


def _run_locked_gate(
    *,
    samples_path: Path,
    min_samples: int,
    min_pearson: float,
    max_mae: float,
    lock_path: Path,
) -> dict:
    if not lock_path.exists():
        return {
            "pass": False,
            "reason": "lock_missing",
            "mode": "locked",
            "lock_path": str(lock_path),
        }

    samples = load_samples(samples_path)
    if len(samples) < min_samples:
        return {
            "pass": False,
            "reason": "insufficient_samples",
            "mode": "locked",
            "sample_count": len(samples),
            "required_min_samples": min_samples,
        }

    try:
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {
            "pass": False,
            "reason": "lock_parse_error",
            "mode": "locked",
            "lock_path": str(lock_path),
        }

    if not bool(lock.get("approved")):
        return {
            "pass": False,
            "reason": "lock_not_approved",
            "mode": "locked",
            "lock_path": str(lock_path),
        }

    actual_hash = _samples_sha256(samples_path)
    expected_hash = str(lock.get("samples_sha256") or "")
    if not expected_hash or actual_hash != expected_hash:
        return {
            "pass": False,
            "reason": "samples_hash_mismatch",
            "mode": "locked",
            "expected_hash": expected_hash,
            "actual_hash": actual_hash,
        }

    locked_sample_count = int(lock.get("sample_count") or 0)
    if locked_sample_count != len(samples):
        return {
            "pass": False,
            "reason": "sample_count_mismatch",
            "mode": "locked",
            "sample_count": len(samples),
            "locked_sample_count": locked_sample_count,
        }

    pearson_r = round(float(lock.get("pearson_r") or 0.0), 4)
    mae = round(float(lock.get("mae") or 1.0), 4)
    passed = pearson_r >= min_pearson and mae <= max_mae
    return {
        "pass": passed,
        "mode": "locked",
        "sample_count": len(samples),
        "pearson_r": pearson_r,
        "mae": mae,
        "thresholds": {
            "min_pearson": min_pearson,
            "max_mae": max_mae,
            "min_samples": min_samples,
        },
        "approved_at": lock.get("approved_at"),
        "approved_by": lock.get("approved_by"),
        "method": "prompt_judge_lock_v1",
    }


def run_gate(
    *,
    samples_path: Path,
    mode: str,
    min_samples: int,
    min_pearson: float,
    max_mae: float,
    require_judge_mode: bool,
    lock_path: Path | None = None,
) -> dict:
    if require_judge_mode and mode not in {"judge", "locked"}:
        return {
            "pass": False,
            "reason": "strict_mode_required",
            "mode": mode,
        }

    if mode == "locked":
        return _run_locked_gate(
            samples_path=samples_path,
            min_samples=min_samples,
            min_pearson=min_pearson,
            max_mae=max_mae,
            lock_path=lock_path or _default_lock_path(samples_path),
        )

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
    parser.add_argument("--mode", choices=["judge", "heuristic", "locked"], default="heuristic")
    parser.add_argument(
        "--lock",
        default=str(
            Path(__file__).resolve().parents[2] / "docs" / "prompt_judge_calibration.lock.json"
        ),
        help="Path to the approved prompt-judge calibration lock file.",
    )
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
        lock_path=Path(args.lock),
    )
    print(json.dumps(result, indent=2))
    if not result.get("pass", False):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
