# Release checklist — private beta

## Pre-deploy

1. Backup Postgres (`scripts/backup-db.sh` or managed snapshot).
2. Confirm `PROMPTCODE_DEBUG=false`, strong `PROMPTCODE_JWT_SECRET`, real `PROMPTCODE_DATABASE_URL`.
3. Set `PROMPTCODE_BETA_INVITE_REQUIRED=true` and create invites: `python backend/scripts/create_invite.py`.
4. Set `PROMPTCODE_INTERVIEW_INTERNAL_TOKEN`, `PROMPTCODE_METRICS_TOKEN`, CORS origins, `DOMAIN`.
5. Set `PROMPTCODE_APP_VERSION` and `PROMPTCODE_GIT_SHA` (or `GIT_SHA`) for diagnostics/feedback.
6. Build interview runner images if `PROMPTCODE_RUNNER=docker`.

## Deploy sequence

1. **Backup** DB
2. **Build** app / images
3. **Migrate**: `cd backend && alembic upgrade head` (never destructive auto-migrate on startup)
4. **Start** API + reverse proxy (HTTPS)
5. **Health**: `GET /health`, `GET /health/ready`
6. **Smoke**: `python backend/scripts/beta_smoke.py` (+ optional invite path)

## Rollback constraints

- Prefer rolling back app image/process; keep DB forward-compatible.
- Do not run destructive downgrades against production data unless rehearsed.
- Score changes require explicit reviewed version bump — never silent rescoring of history.

## Post-deploy

1. Schedule cleanup: cron/systemd `python backend/scripts/cleanup_interview_sessions.py` (hourly recommended).
2. Confirm backup retention (daily, ≥7 days local or managed).
3. Hit `/api/interview/internal/diagnostics` with internal token.
4. Invite cohort; watch funnel + infra tags — do not rewrite product mid-beta.
