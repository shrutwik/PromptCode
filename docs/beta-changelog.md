# Beta changelog

## 2026-09-18 — Private beta ops

- Invite codes + optional email allowlist (`PROMPTCODE_BETA_INVITE_REQUIRED`)
- User cohort fields: `beta_cohort`, `signup_source`, `invite_code_id`
- Product analytics events + funnel / challenge quality aggregates (internal)
- Calibration overview, session review, human review (separate from automated score)
- Feedback fields: AI expected, confusing/broken, most-like-real-interview
- Optional abandon reason; infra failure tags; wall/active/infra-blocked durations
- Persist `scoring_version=v1` and `challenge_version` on sessions/evaluations
- Internal user list/disable/enable; anonymized calibration export
- Docs: release checklist, ops alert thresholds, challenge revision workflow

Score changes are **explicit / reviewed / versioned** only — no auto-recalibrate from recent users.
