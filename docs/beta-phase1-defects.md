# Beta Phase 1 — Defects (before modification)

Verified 2026-09-18 with `.venv` (system Python fails: Pydantic ForwardRef / recursive_guard mismatch).

## Verification results
- `verify_interview_mvp.py`: **PASS** (registry=10, score path OK)
- `pytest tests/test_interview_mvp.py`: **8 passed**
- `pytest tests/test_interview_production.py`: **13 passed, 1 skipped** (Docker E2E skip expected without daemon/images)

## Defects / gaps for small real-user beta

1. **Anonymous session ownership** — `POST /api/interview/sessions` uses `get_optional_user`; `user_id` nullable; `owner_token` alone grants access. Cross-user ID guessing partially mitigated, but unauthenticated workspace APIs violate beta authz.
2. **User model incomplete for beta** — missing `display_name`, `last_login_at`, `beta_status`.
3. **No session TTL / expired state** — statuses used loosely (`active`/`submitted`); no `PROMPTCODE_SESSION_TTL_HOURS`, no expire transition, no immutable edit gate for expired.
4. **No interview workspace cleanup service** — workspaces can accumulate; Docker IsolatedRunner already removes containers in `finally`, but no orphan/expired workspace sweeper.
5. **Bearer tokens in browser storage** — access/refresh in `sessionStorage` (migrated off localStorage). No HttpOnly cookies; acceptable if documented, but prod should prefer cookies or accept documented bearer risk.
6. **No `/health/ready`** — only `/health`; no DB/runner-config readiness split.
7. **No interview feedback persistence** — post-challenge realism/difficulty/text not stored.
8. **No attempt numbering** — multiple sessions per challenge OK, but no `attempt_number` / clear attempt UX.
9. **No first-run onboarding / privacy notice** for interview product surface.
10. **Missing beta ops docs** — need `docs/deployment.md`, `docs/security.md`, `docs/beta-operations.md`; interview-specific env vars incomplete in example.
11. **Interview concurrency** — no `PROMPTCODE_MAX_RUNNERS` semaphore for interview Docker runs (sandbox has concurrency; interview path may not).
12. **Authz test coverage for interview** — MVP tests cover isolation/scoring; lack unauth + cross-user matrix for sessions/files/AI/tests/report/defend.

## Non-defects (preserve)
- FastAPI + vanilla JS + Monaco interview UX
- IsolatedRunner Docker architecture + allowlists
- AIProvider mock/production
- Existing scoring/events/signals
- Existing email/password JWT auth (bcrypt), rate limits, CORS/CSP middleware, metrics token gate
- Challenge corpus (10 Medium)

## Constraint
Do not redesign interview UX or regenerate challenges. Extend auth/ownership/lifecycle/config only.
