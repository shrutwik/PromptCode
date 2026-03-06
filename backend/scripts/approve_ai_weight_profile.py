"""Approve and lock an AI weight profile after calibration review.

Usage:
    cd backend && python -m scripts.approve_ai_weight_profile \
      --reviewer "alice" \
      --calibration-report /tmp/prompt_judge_gate.json
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from app.services.evaluation.weight_profile import _profile_hash


def _load_json(path: Path) -> dict:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object at {path}")
    return data


def _display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(Path.cwd()))
    except Exception:
        return str(path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Approve and lock AI weight profile")
    parser.add_argument(
        "--profile",
        default=str(Path(__file__).resolve().parents[1] / "benchmarks" / "ai_weight_profile.json"),
        help="Path to ai_weight_profile.json",
    )
    parser.add_argument(
        "--lock",
        default=str(Path(__file__).resolve().parents[1] / "benchmarks" / "ai_weight_profile.lock.json"),
        help="Output lock-file path",
    )
    parser.add_argument("--reviewer", required=True, help="Reviewer or approver handle")
    parser.add_argument(
        "--calibration-report",
        default="",
        help="Path to JSON output from run_prompt_judge_calibration_gate",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Allow approval without a passing calibration report",
    )
    args = parser.parse_args()

    profile_path = Path(args.profile)
    lock_path = Path(args.lock)
    if not profile_path.exists():
        raise SystemExit(f"Profile file not found: {profile_path}")

    profile = _load_json(profile_path)
    version = str(profile.get("version") or "").strip()
    if not version:
        raise SystemExit("Profile file must include a non-empty 'version'")

    calibration_info: dict = {}
    if args.calibration_report:
        report_path = Path(args.calibration_report)
        if not report_path.exists():
            raise SystemExit(f"Calibration report not found: {report_path}")
        calibration_info = _load_json(report_path)
        if not args.force:
            if calibration_info.get("pass") is not True:
                raise SystemExit("Calibration report did not pass; refusing to approve profile.")
            if str(calibration_info.get("mode") or "") != "judge":
                raise SystemExit("Calibration report mode must be 'judge' for approval.")
    elif not args.force:
        raise SystemExit("Calibration report is required unless --force is supplied.")

    lock = {
        "approved": True,
        "approved_at": datetime.now(timezone.utc).isoformat(),
        "approved_by": str(args.reviewer).strip(),
        "approved_version": version,
        "profile_sha256": _profile_hash(profile),
        "profile_path": _display_path(profile_path),
        "calibration_gate": {
            "mode": str(calibration_info.get("mode") or ""),
            "pass": bool(calibration_info.get("pass")) if calibration_info else None,
            "sample_count": calibration_info.get("sample_count"),
            "pearson_r": calibration_info.get("pearson_r"),
            "mae": calibration_info.get("mae"),
        },
        "force": bool(args.force),
    }

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
    print(f"Saved lock file: {lock_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
