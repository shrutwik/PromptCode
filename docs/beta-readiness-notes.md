# Beta readiness — implementation notes

## Phase 1 defects
See `docs/beta-phase1-defects.md`.

## Authentication architecture
- Extended existing FastAPI email/password JWT auth (bcrypt).
- Signup/login/logout/me; `last_login_at`, `display_name`, `beta_status` on User.
- Bearer tokens remain primary for the vanilla SPA (`sessionStorage`, migrated off localStorage).
- Optional HttpOnly cookies via `PROMPTCODE_AUTH_COOKIE_ENABLED` (`pc_access_token` / `pc_refresh_token`).

## Authorization model
- Challenge catalog remains public; starting sessions and all workspace/AI/test/report/defend/dashboard APIs require auth.
- Ownership: `session.user_id == auth user`; cross-user → 404.

## Database changes
- Migration `f8a9b0c1d2e3_beta_auth_session_lifecycle.py` (non-destructive).
- Session: `attempt_number`, `expires_at`, resource counters, feedback fields.

## Session lifecycle
- States: created/active/submitted/expired/failed.
- TTL: `PROMPTCODE_SESSION_TTL_HOURS` (default 24); mutations blocked when expired.
- Submit idempotent; submitted code immutable.

## Cleanup strategy
- `backend/app/services/interview/cleanup.py` + `scripts/cleanup_interview_sessions.py`
- Removes expired/failed/orphan workspaces + stopped PromptCode interview containers; keeps DB history and challenges/.

## Deployment / observability
- Docs: `docs/deployment.md`, `docs/security.md`, `docs/beta-operations.md`
- `/health`, `/health/ready`, `/ready`; internal diagnostics; request IDs; metrics token gate preserved.
- Runner concurrency semaphore (`PROMPTCODE_MAX_RUNNERS`).

## Frontend
- Auth-aware `interview-api.js`; onboarding/privacy/settings pages; challenge progress + resume; report feedback.

## Tests
- MVP + production + authz + health readiness passing under `.venv`.
- `backend/scripts/beta_smoke.py` isolated sqlite smoke (Docker E2E not required).
