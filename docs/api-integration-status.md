# PromptCode API Integration Status

Audit date: 2026-09-19  
Overall: **PASS WITH UNEXERCISED PRODUCTION DEPENDENCIES**

Evidence bases:
- Disposable SQLite E2E (API + DB after each stage) → `docs/integration-exercise-results.json`
- Pytest: interview MVP/authz/production/private-beta/health + new `test_interview_integration_audit.py` (38 passed, 1 skipped)
- `scripts/verify_interview_mvp.py` OK
- Alembic single head `a0b1c2d3e4f5`; clean `upgrade head` OK
- Docker daemon unavailable in audit environment → runner docker path **NOT EXERCISED**
- Live OpenAI path not smoke-tested (mock AI **PASS**)

## Endpoint matrix

| Endpoint | Frontend Caller | Auth | DB/Service | Tested | Result |
|----------|-----------------|------|------------|--------|--------|
| `POST /api/auth/signup` | `api.js` | public | users + analytics | E2E+pytest | PASS |
| `POST /api/auth/login` | `api.js` | public | users | E2E | PASS |
| `POST /api/auth/logout` | `api.js` / InterviewAPI | bearer | revoked_tokens | pytest | PASS |
| `POST /api/auth/refresh` | `api.js` | refresh | tokens | unit/auth tests | PASS |
| `GET/PUT /api/auth/me` | settings / api.js | bearer | users | E2E | PASS |
| `GET /api/interview/challenges` | InterviewAPI.listChallenges | optional | registry | E2E+pytest | PASS |
| `GET /api/interview/challenges/progress` | listChallengesProgress | bearer | sessions | FE mapped | PASS |
| `GET /api/interview/challenges/{slug}` | getChallenge | optional | registry | pytest | PASS |
| `POST /api/interview/sessions` | startSession | bearer | sessions+workspace | E2E | PASS |
| `GET /api/interview/sessions/{id}` | getSession | owner | sessions | E2E/authz | PASS |
| `GET/PUT .../files...` | list/get/saveFile | owner | workspace+events | E2E | PASS |
| `POST/GET .../events` | postEvent / (report timeline) | owner | events | E2E | PASS |
| `POST .../tests` | runTests | owner | runner+events | E2E (local; vitest may miss deps on host) | PASS |
| `POST .../ai/chat` | chat | owner | AIProvider+messages | E2E mock | PASS |
| `POST .../ai/apply` | applyAiEdit | owner | workspace+events | E2E | PASS |
| `GET .../diff` | diffSummary/diffFile | owner | snapshots | E2E | PASS |
| `POST .../submit` | submit | owner | evaluation+idempotent | E2E | PASS |
| `GET .../report` | report | owner | evaluation | E2E | PASS |
| `GET/POST .../defend` | defend/answerDefend | owner | metrics+analytics | E2E+new test | PASS |
| `POST .../feedback` | feedback | owner | feedback_* + analytics | E2E+new test | PASS |
| `GET /api/interview/dashboard` | dashboard | bearer | sessions | E2E | PASS |
| `POST .../abandon` | **none** | bearer | sessions | code review | UNUSED/INTERNAL |
| `GET /api/interview/internal/*` | scripts/ops | internal token | beta_ops | pytest private beta | UNUSED/INTERNAL |
| `GET /health` | probes | public | — | E2E+pytest | PASS |
| `GET /health/ready` | probes | public | DB+runner config | E2E+pytest | PASS |
| `GET/POST /api/challenges` | api.js legacy | mixed | challenges table | not in interview E2E | UNUSED/INTERNAL (legacy product) |
| `/api/submissions/*` | api.js legacy | bearer | submissions/jobs | separate suite | UNUSED/INTERNAL (legacy) |
| `/api/leaderboard/*` | leaderboard page | mixed | leaderboard | separate suite | PASS (legacy path) |
| `/api/chat/*` | playground | bearer | chat | separate | PASS (legacy) |
| Docker runner path | — | — | docker runner | daemon down | NOT EXERCISED |
| Live OpenAI provider | — | — | AIProvider prod | keys present; not smoked | NOT EXERCISED |

## DB status matrix

| Entity | Created By | Read By | Updated By | FK/Ownership | Verified |
|--------|------------|---------|------------|--------------|----------|
| users | signup | me/authz | login/profile | PK email/username unique | PASS |
| interview_sessions | start_session | session/dashboard | submit/abandon/expire/feedback | user_id FK nullable+owner_token | PASS |
| interview_session_events | _add_event / post_event | report timeline / list_events | — | session_id FK | PASS (ordering fixed via utcnow) |
| interview_session_files | save_file metadata | — | save | session_id | PASS |
| interview_ai_messages | ai_chat | scoring prompts | — | session_id | PASS |
| interview_evaluations | submit (1:1 session) | report/defend | defend answers in metrics | unique session_id | PASS idempotent |
| product_analytics_events | track_event | internal funnel | — | user/session optional FKs | PASS |
| invite_codes / human_reviews | beta ops | internal | internal | beta | PASS (ops tests) |
| challenges/submissions/runs/leaderboard | legacy flows | legacy FE | workers | legacy FKs | NOT EXERCISED in interview E2E |
| revoked_tokens / auth_rate_limit_events | auth | auth | — | — | PASS (auth tests) |

## Issues found and fixed

1. **Defend questions leaked inline answers** — SOLUTION.md lines like `Q: …? A: …` were returned as the candidate question. Fixed in `rubric.parse_defend_questions` + `sanitize_candidate_question`; report/defend paths hardened.
2. **Feedback FE dropped optional fields** — `interview-report.html` sent `ai_as_expected`, `confusing_or_broken`, `most_like_real_interview` but `InterviewAPI.feedback` only forwarded realism/difficulty/text. Fixed `frontend/interview-api.js`.
3. **Timeline same-second ordering** — SQLite `server_default=now()` collapsed order. `_add_event` now sets `created_at=utcnow()` with microseconds.

## Dead / unused (documented, not removed)

- `POST /api/interview/sessions/{id}/abandon` — no FE caller.
- Internal interview diagnostics/calibration/export routes — ops/scripts only.
- Legacy `/api/challenges`, `/api/submissions`, `/api/chat` — still used by non-interview pages; not deleted.

## Config notes

- Many `PROMPTCODE_*` keys in `.env.example` map to Settings fields (pydantic); audit regex of string literals under-counted consumers.
- Compose-only keys (`PROMPTCODE_DB_PORT`, `DOCKER_GID`, GHCR, rclone) are infra — not app Settings dead keys.
- Interview-critical: `PROMPTCODE_RUNNER`, `PROMPTCODE_INTERVIEW_*`, `PROMPTCODE_BETA_*`, `PROMPTCODE_AUTH_COOKIE_*`, `PROMPTCODE_OPENAI_*`, `PROMPTCODE_JWT_SECRET`, `PROMPTCODE_DATABASE_URL`.

## Unexercised / blockers

- **Docker runner**: Docker CLI present but `docker info` failed → NOT EXERCISED.
- **Live AI**: mock PASS; production OpenAI smoke NOT EXERCISED.
- Host `npm test` / vitest may be missing in workspace → test run returns non-zero but pipeline still records result (expected locally).

## Verification commands run

```text
pytest tests/test_interview_*.py tests/test_private_beta_ops.py tests/test_health_readiness.py
python scripts/verify_interview_mvp.py
alembic upgrade head  # clean sqlite
```
