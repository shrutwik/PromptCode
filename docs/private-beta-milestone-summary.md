# Private-beta milestone — handoff summary

## Completed

Private-beta access, analytics, calibration, deploy docs, versioning, ops visibility — surgical extensions on prior beta auth/lifecycle. No interview UX / scoring architecture rewrite.

## Private-beta access model

- Invite codes (`invite_codes`) + optional `PROMPTCODE_BETA_EMAIL_ALLOWLIST`
- Gate: `PROMPTCODE_BETA_INVITE_REQUIRED=true` (existing users unaffected)
- Failed invite → generic 403 (no config leak)
- Tracks `beta_cohort`, `signup_source`, `invite_code_id`, `created_at`
- CLI: `backend/scripts/create_invite.py`, `beta_users.py`

## Deployment architecture

- Reverse proxy/HTTPS + FastAPI + Postgres + Docker runner (documented)
- Shared-host Docker socket risk documented
- Backup via `scripts/backup-db.sh` / managed preferred
- Sequence: backup → build → `alembic upgrade head` → start → health → smoke
- See `docs/release-checklist.md`, `docs/deployment.md`

## Analytics added

- Table `product_analytics_events` (separate from interview timeline)
- Events: signup, login, library/detail, session start/abandon/submit, report, defend, feedback
- Internal: `/internal/analytics/funnel`, `/internal/analytics/challenges`

## Calibration tooling

- `/internal/calibration`, `/internal/calibration/disagreements`
- `/internal/sessions/{id}/review` GET/POST (human_review ≠ automated_score)
- CLI: `backend/scripts/review_session.py`
- Anomaly flags (short/long time, infra, identical scores, correctness mismatch)
- Anonymized export: `/internal/export/calibration`

## Challenge/versioning changes

- `challenge_version` persisted on sessions (from registry version)
- Workflow: `docs/challenge-revision-workflow.md`
- No challenge corpus regeneration

## Scoring/versioning changes

- `scoring_version=v1` on sessions + evaluations
- No silent rescoring / no auto-calibrate from recent users
- Changelog: `docs/beta-changelog.md`

## Operational monitoring

- Diagnostics include version/git_sha; `/internal/incidents`, `/internal/disk`
- Alert thresholds in `docs/beta-operations.md`
- Cleanup cron documented

## Smoke-test result

- `verify_interview_mvp.py` → OK
- Interview-related pytest → **35 passed**, 1 skipped
- `beta_smoke.py` → **SMOKE OK** (Docker E2E not required / skipped)
- `alembic upgrade head` on clean sqlite → head `a0b1c2d3e4f5`
- Pre-existing unrelated failures remain (SDK samples, quality gates, etc.)

## Known beta risks

- Bearer tokens in sessionStorage (cookie mode optional)
- Docker socket privilege on runner host
- Small-n analytics noise
- Local runner default unless images built

## Exact deployment steps

1. Backup DB
2. Set env (JWT, DB, CORS, DOMAIN, invite gate, internal/metrics tokens, APP_VERSION, GIT_SHA)
3. Build images if docker runner
4. `alembic upgrade head`
5. Start API + HTTPS proxy
6. Health + smoke
7. Schedule cleanup cron
8. `create_invite.py` and invite cohort

## Recommended beta cohort size

**10–25 users**, target **≥50 sessions**, **≥10 human reviews**, infra fail **<5%**.

## What data to review after first 10 sessions

Funnel rates, per-challenge abandon/infra tags, 3–5 session reviews + anomaly flags, automated vs human disagreements, feedback realism/difficulty, disk/cleanup health.

## Recommended action after

Invite real users → observe → manually review evidence → calibrate from data. **Do not** major-rewrite unless beta evidence requires it.
