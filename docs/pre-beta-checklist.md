# Pre-beta checklist (private cohort)

Short actionable gate before inviting users. Product UI is freeze-candidate.

## Must be true
- [x] `alembic upgrade head` on target DB
- [x] `GET /health` + `GET /health/ready` OK
- [x] Interview pytest subset green (`test_interview_*` + `test_private_beta_ops`)
- [x] Auth: signup/login → dashboard → challenges → start session
- [x] Session: edit file → run tests → AI chat → Review diff → submit → report → feedback
- [x] Cross-user session access returns 404 (no existence leak)
- [x] Report scrubber loads with real events
- [x] Chartreuse brand + cool AI blue + semantic success green distinct

## Configure before invites
- [ ] Set `PROMPTCODE_AI_PROVIDER=openai` (or production provider) **and** real `PROMPTCODE_OPENAI_API_KEY` if you want live AI (local QA used **mock**)
- [ ] Build runner images if using Docker:
  - `docker/Dockerfile.interview-node` → `promptcode-runner-node:latest`
  - `docker/Dockerfile.interview-python` → `promptcode-runner-python:latest`
  - Set `PROMPTCODE_RUNNER=docker`
- [ ] Production: `PROMPTCODE_DEBUG=false`, non-placeholder JWT, explicit CORS, prefer `PROMPTCODE_AUTH_COOKIE_ENABLED=true`
- [ ] Create invites / beta users (`backend/scripts/create_invite.py`, `beta_users.py`)
- [ ] Confirm cleanup cron (`cleanup_interview_sessions.py`) scheduled

## Nice-to-have (non-blocking)
- [ ] Resolve 5 legacy full-suite failures (SDK guide samples, sandbox executor token validation, prompt-judge freshness, release quality gates)
- [ ] Keyboard-complete defend + submit modal pass
- [ ] Low-power device landing perf spot-check

## Go decision
**GO** when Must-be-true is checked and Configure items for *your* host are done.

**Exact next step:** freeze the product UI, invite the first private-beta cohort, and review real sessions before making additional product changes.
