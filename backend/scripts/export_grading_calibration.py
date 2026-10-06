"""Protected operator export of evidence-bound pairs of real human reviews."""
from __future__ import annotations

import argparse
import asyncio
import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select

from app.db.session import async_session_factory
from app.models.interview_grading import InterviewGradingJob, InterviewGradeReview
from app.models.user import User
from app.services.interview.calibration import challenge_version_for
from app.services.interview.grading import HumanReview, RUBRIC_VERSION, score_reviewed_assessment
from app.services.interview.grading_review import review_context
from app.services.interview.trusted_cases import VERSION, inventory_digest


async def export_calibration_records(db, *, confirm_real_pilot: bool = False) -> dict:
    """No prompts/source/person names. Import only genuine, independently collected pilots.

    The flag is an operator attestation, not automatic proof of real participation
    or blinded review. Review/evaluator authenticity is checked from stored records.
    """
    result = {"records": [], "rubric_version": RUBRIC_VERSION,
              "generated_at": datetime.now(timezone.utc).isoformat(),
              "real_pilot_attested": confirm_real_pilot,
              "notice": "Operator must establish independent blinded human ratings and real pilot participation."}
    if not confirm_real_pilot:
        return {**result, "status": "real_pilot_confirmation_required", "excluded": {}}
    jobs = (await db.execute(select(InterviewGradingJob.session_id).where(
        InterviewGradingJob.status == "completed").order_by(InterviewGradingJob.created_at).limit(5000))).scalars().all()
    excluded = Counter()
    for session_id in jobs:
        try:
            session, job, _, assessment = await review_context(db, session_id, None)
            payload = job.result["payload"]
            if (job.challenge_version != challenge_version_for(job.challenge_slug)
                    or payload["evaluator_version"] != VERSION
                    or payload["inventory_digest"] != inventory_digest(job.challenge_slug)):
                raise ValueError("stale_deployed_version")
            rows = (await db.execute(select(InterviewGradeReview).where(
                InterviewGradeReview.session_id == session.id,
                InterviewGradeReview.source_digest == job.source_digest,
                InterviewGradeReview.packet_digest == assessment["packet_digest"])
                .order_by(InterviewGradeReview.revision))).scalars().all()
            pairs = []
            seen = set()
            for row in rows:
                # Earliest complete review for each reviewer avoids cherry-picking
                # revised ratings to inflate agreement statistics.
                if row.reviewer_id in seen or row.reviewer_id == session.user_id:
                    continue
                reviewer = await db.get(User, row.reviewer_id)
                if not reviewer or reviewer.role != "interviewer":
                    continue
                review_data = {k: v for k, v in row.review.items() if k != "manual_checks"}
                try:
                    review = HumanReview.model_validate(review_data)
                    if review.reviewer_id != str(row.reviewer_id):
                        continue
                    score_reviewed_assessment(assessment, review)
                except (ValueError, TypeError, KeyError):
                    continue
                seen.add(row.reviewer_id)
                pairs.append({"reviewer_id": review.reviewer_id, "reviewer_kind": "human",
                              "packet_digest": review.packet_digest,
                              "ratings": {key: value.rating for key, value in review.dimensions.items()}})
                if len(pairs) == 2:
                    break
            if len(pairs) != 2:
                raise ValueError("two_independent_current_reviews_required")
            result["records"].append({"attempt_id": str(session.id), "challenge_slug": job.challenge_slug,
                "challenge_version": job.challenge_version, "rubric_version": RUBRIC_VERSION,
                "synthetic": False, "external_verified": True, "snapshot_digest": job.source_digest,
                "packet_digest": assessment["packet_digest"], "evaluator_version": VERSION,
                "inventory_digest": payload["inventory_digest"],
                "ai_available": bool(assessment["packet"].get("ai_available")), "reviews": pairs})
        except HTTPException:
            excluded["evidence_not_verified"] += 1
        except (ValueError, KeyError, TypeError, OSError) as exc:
            label = str(exc) if str(exc) in {"stale_deployed_version", "two_independent_current_reviews_required"} else "invalid_review_evidence"
            excluded[label] += 1
        finally:
            # Export is read-only; release per-attempt consistency locks promptly.
            await db.rollback()
    return {**result, "status": "exported", "excluded": dict(excluded),
            "completed_jobs_considered": len(jobs)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True, help="Protected JSON export path")
    parser.add_argument("--confirm-real-pilot", action="store_true",
                        help="Attest records are real pilot attempts, not synthetic fixtures")
    args = parser.parse_args()
    async def export():
        async with async_session_factory() as db:
            return await export_calibration_records(db, confirm_real_pilot=args.confirm_real_pilot)
    result = asyncio.run(export())
    target = Path(args.output)
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as output:
        os.fchmod(output.fileno(), 0o600)
        output.write(json.dumps(result, indent=2) + "\n")
    print(f"Exported {len(result['records'])} paired attempts; status: {result['status']}.")
    return 0 if args.confirm_real_pilot else 1


if __name__ == "__main__":
    raise SystemExit(main())
