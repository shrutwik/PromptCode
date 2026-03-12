"""Approve and lock a prompt-judge calibration report for deterministic strict gates."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from scripts.run_prompt_judge_calibration_gate import _samples_sha256


def _load_json(path: Path) -> dict:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve prompt-judge calibration")
    parser.add_argument(
        "--samples",
        default=str(Path(__file__).resolve().parents[2] / "docs" / "prompt_judge_samples.jsonl"),
        help="Path to prompt_judge_samples.jsonl",
    )
    parser.add_argument(
        "--lock",
        default=str(Path(__file__).resolve().parents[2] / "docs" / "prompt_judge_calibration.lock.json"),
        help="Output lock-file path",
    )
    parser.add_argument("--reviewer", required=True, help="Reviewer or approver handle")
    parser.add_argument(
        "--calibration-report",
        required=True,
        help="Path to JSON output from run_prompt_judge_calibration_gate",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow approval of a non-passing calibration report.",
    )
    args = parser.parse_args()

    samples_path = Path(args.samples)
    report_path = Path(args.calibration_report)
    lock_path = Path(args.lock)

    if not samples_path.exists():
        raise SystemExit(f"Samples file not found: {samples_path}")
    if not report_path.exists():
        raise SystemExit(f"Calibration report not found: {report_path}")

    report = _load_json(report_path)
    if not args.force and report.get("pass") is not True:
        raise SystemExit("Calibration report did not pass; refusing to approve lock.")

    sample_count = sum(
        1 for line in samples_path.read_text(encoding="utf-8").splitlines() if line.strip()
    )
    lock = {
        "approved": True,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": str(args.reviewer).strip(),
        "mode": str(report.get("mode") or ""),
        "sample_count": sample_count,
        "samples_path": str(samples_path),
        "samples_sha256": _samples_sha256(samples_path),
        "pearson_r": report.get("pearson_r"),
        "mae": report.get("mae"),
        "pass": bool(report.get("pass")),
        "force": bool(args.force),
    }

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"Saved lock file: {lock_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
