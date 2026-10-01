# Beta success criteria & calibration questions

## Targets (directional)

| Signal | Target |
|--------|--------|
| Invited users who sign up | 10–25 |
| Completed sessions | ≥50 |
| Infra fail rate (runner/docker/AI tagged) | <5% of sessions |
| Human-reviewed sessions | ≥10 |
| Feedback response rate | ≥30% of submitted |

Small samples → treat rates as signals, not conclusions.

## Questions beta should answer

1. Do candidates understand the workspace without coaching?
2. Is intended difficulty/time close to observed medians?
3. Do rubric scores match human judgment (≥10 reviews)?
4. Are infra failures rare and correctly tagged (not scored)?
5. Does invite gate + disable work without leaking config?
6. Is “Practice Interview” language clear (no hiring claims)?
7. Which 1–2 challenges need revision first?

## After first 10 sessions — review

- Funnel: signup → start → submit → report → defend → feedback
- Per-challenge abandon + infra tags
- 3–5 session reviews with anomaly flags
- Any disagreement between automated_score and human_review
- Disk/cleanup health

**Next action:** invite real users; observe; calibrate from evidence. Do not major-rewrite unless beta evidence requires it.
