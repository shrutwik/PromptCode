# Private-beta milestone — defects before change

Verified 2026-09-18 with `.venv`:

- `python backend/scripts/verify_interview_mvp.py` → OK (registry=10, score path works)
- `pytest` → 310 passed, 5 failed (pre-existing non-interview: SDK sample paths, sandbox token validation, prompt-judge freshness, release quality gates)
- Migration head: `f8a9b0c1d2e3` (prior beta auth/lifecycle)

## Gaps for private beta deploy (this milestone)

1. No invite codes / email allowlist gate on signup (public signup still open)
2. No `beta_cohort` / `signup_source` / `invite_code_id` on users
3. No product analytics events (separate from interview timeline)
4. No funnel / per-challenge quality aggregates
5. No calibration view / anomaly flags / disagreement report
6. No human review override (separate from automated score)
7. Feedback form missing AI-expected / confusing / “most like real interview”
8. No abandonment reason capture
9. Infra failure tagging / wall vs active vs blocked duration incomplete
10. No lightweight beta user list/disable CLI beyond `beta_status` on login
11. Missing release checklist, backup/restore, version in diagnostics, alert thresholds docs
12. No `scoring_version` / `challenge_version` persistence
13. No anonymized calibration export
14. Landing / Practice Interview labeling / report language audit incomplete
15. No documented beta success criteria

## Non-goals (do not rewrite)

Interview workspace UX, challenge corpus regen, FastAPI/frontend stack, scoring architecture, enterprise features, K8s.
