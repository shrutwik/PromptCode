"""Calibrate prompt-quality judge against human-rated samples.

Usage:
    cd backend && python -m scripts.calibrate_prompt_judge --samples ../docs/prompt_judge_samples.jsonl
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from statistics import mean

from app.services.evaluation.prompt_quality import _heuristic_score, _judge_with_llm


def load_samples(path: Path) -> list[dict]:
    rows: list[dict] = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        rows.append(json.loads(line))
    return rows


def evaluate_sample(sample: dict, mode: str) -> float:
    prompts = sample.get("prompts", [])
    challenge_description = sample.get("challenge_description", "")
    if mode == "heuristic":
        result = _heuristic_score(prompts)
    else:
        result = _judge_with_llm(prompts, challenge_description)
    return float(result.get("overall", 0.0))


def pearson(xs: list[float], ys: list[float]) -> float:
    if not xs or len(xs) != len(ys):
        return 0.0
    x_mean = mean(xs)
    y_mean = mean(ys)
    num = sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, ys))
    den_x = sum((x - x_mean) ** 2 for x in xs) ** 0.5
    den_y = sum((y - y_mean) ** 2 for y in ys) ** 0.5
    if den_x == 0 or den_y == 0:
        return 0.0
    return num / (den_x * den_y)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", required=True, help="Path to JSONL samples")
    parser.add_argument("--mode", choices=["judge", "heuristic"], default="judge")
    args = parser.parse_args()

    samples = load_samples(Path(args.samples))
    if not samples:
        raise SystemExit("No samples found")

    human: list[float] = []
    model: list[float] = []

    for sample in samples:
        h = float(sample["human_overall"])
        m = evaluate_sample(sample, args.mode)
        human.append(h)
        model.append(m)

    mae = mean(abs(h - m) for h, m in zip(human, model))
    corr = pearson(human, model)

    print(json.dumps(
        {
            "sample_count": len(samples),
            "mode": args.mode,
            "mae": round(mae, 4),
            "pearson_r": round(corr, 4),
            "mean_human": round(mean(human), 4),
            "mean_model": round(mean(model), 4),
        },
        indent=2,
    ))


if __name__ == "__main__":
    main()
