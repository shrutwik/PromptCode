"""Challenge publish-quality gate.

Usage:
    cd backend && python -m scripts.run_challenge_publish_gate
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _count_hidden_cases(hidden_tests: Any) -> int:
    if isinstance(hidden_tests, list):
        return len(hidden_tests)
    if isinstance(hidden_tests, dict):
        total = 0
        for cases in hidden_tests.values():
            if isinstance(cases, list):
                total += len(cases)
        return total
    return 0


def run_gate(
    *,
    challenges_dir: Path,
    expected_challenges: int = 10,
    min_hidden_cases: int = 2,
    min_input_examples: int = 1,
) -> dict[str, Any]:
    files = sorted(challenges_dir.glob("*/challenge.json"))
    violations: list[dict[str, Any]] = []
    per_challenge: list[dict[str, Any]] = []

    if len(files) != expected_challenges:
        violations.append({
            "scope": "global",
            "reason": "unexpected_challenge_count",
            "expected": expected_challenges,
            "actual": len(files),
        })

    required_root = {
        "slug",
        "title",
        "description",
        "difficulty",
        "category",
        "constraints",
        "sample_input",
        "sample_output",
        "config",
    }
    required_config = {
        "accuracy_mode",
        "expected_calls",
        "processing_rules",
        "inputs",
        "ground_truth",
        "hidden_tests",
    }

    seen_slugs: set[str] = set()
    for path in files:
        row: dict[str, Any] = {
            "file": str(path),
            "ok": True,
            "issues": [],
        }
        try:
            payload = json.loads(path.read_text())
        except Exception as exc:
            row["ok"] = False
            row["issues"].append(f"invalid_json:{exc}")
            per_challenge.append(row)
            violations.append({"scope": str(path), "reason": "invalid_json"})
            continue

        missing_root = sorted(required_root - set(payload.keys()))
        if missing_root:
            row["ok"] = False
            row["issues"].append(f"missing_root_keys:{','.join(missing_root)}")

        slug = str(payload.get("slug") or "")
        if not slug:
            row["ok"] = False
            row["issues"].append("missing_slug")
        elif slug in seen_slugs:
            row["ok"] = False
            row["issues"].append("duplicate_slug")
        seen_slugs.add(slug)

        config = payload.get("config") if isinstance(payload.get("config"), dict) else {}
        missing_cfg = sorted(required_config - set(config.keys()))
        if missing_cfg:
            row["ok"] = False
            row["issues"].append(f"missing_config_keys:{','.join(missing_cfg)}")

        expected_calls = int(config.get("expected_calls") or 0)
        if expected_calls < 1 or expected_calls > 8:
            row["ok"] = False
            row["issues"].append("expected_calls_out_of_range")

        max_llm_calls = int((payload.get("constraints") or {}).get("max_llm_calls") or 0)
        if max_llm_calls < 1 or max_llm_calls > 20:
            row["ok"] = False
            row["issues"].append("max_llm_calls_out_of_range")

        inputs = config.get("inputs")
        if not isinstance(inputs, dict) or not inputs:
            row["ok"] = False
            row["issues"].append("inputs_missing_or_empty")
        else:
            inferred_count = 0
            for value in inputs.values():
                if isinstance(value, list):
                    inferred_count = max(inferred_count, len(value))
                elif value:
                    inferred_count = max(inferred_count, 1)
            if inferred_count < min_input_examples:
                row["ok"] = False
                row["issues"].append("too_few_input_examples")

        ground_truth = config.get("ground_truth")
        if ground_truth in (None, "", [], {}):
            row["ok"] = False
            row["issues"].append("ground_truth_missing_or_empty")

        hidden_count = _count_hidden_cases(config.get("hidden_tests"))
        if hidden_count < min_hidden_cases:
            row["ok"] = False
            row["issues"].append("too_few_hidden_tests")
        row["hidden_case_count"] = hidden_count

        if config.get("counterfactual_baseline_enabled") is False:
            row["ok"] = False
            row["issues"].append("counterfactual_baseline_disabled")

        if not row["ok"]:
            violations.append({
                "scope": str(path),
                "reason": "challenge_quality_checks_failed",
                "issues": row["issues"],
            })
        per_challenge.append(row)

    passed = len(violations) == 0
    return {
        "pass": passed,
        "challenge_count": len(files),
        "expected_challenges": expected_challenges,
        "violations": violations,
        "summary": {
            "ok_count": sum(1 for r in per_challenge if r["ok"]),
            "failed_count": sum(1 for r in per_challenge if not r["ok"]),
        },
        "per_challenge": per_challenge,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run challenge publish-quality gate")
    parser.add_argument(
        "--challenges-dir",
        type=Path,
        default=Path(__file__).resolve().parents[2] / "challenges",
    )
    parser.add_argument("--expected-challenges", type=int, default=10)
    parser.add_argument("--min-hidden-cases", type=int, default=2)
    parser.add_argument("--min-input-examples", type=int, default=1)
    args = parser.parse_args()

    result = run_gate(
        challenges_dir=args.challenges_dir,
        expected_challenges=args.expected_challenges,
        min_hidden_cases=args.min_hidden_cases,
        min_input_examples=args.min_input_examples,
    )
    print(json.dumps(result, indent=2))
    return 0 if result["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
