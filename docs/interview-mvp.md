# Interview Simulation MVP

## Architecture choice

**Extend existing FastAPI + vanilla JS + SQLAlchemy/Alembic + Docker stack** instead of introducing Next.js/Prisma/Tailwind.

Why:
- Auth, rate limits, chat/LLM plumbing, static serving, and DB migrations already exist.
- Eval platform (`challenge.json` seeding + `/api/challenges` + sandbox workers) stays untouched.
- Interview flows are additive under `/api/interview/*` and new frontend pages.
- Fastest path to a secure candidate-safe MVP without dual stacks.

## How to run

Quick service check (no full ASGI boot):
```bash
python backend/scripts/verify_interview_mvp.py
```

Full stack:
```bash
# Backend (from repo root, with existing venv/deps)
cd backend
alembic upgrade head   # applies interview_sessions migration
uvicorn app.main:app --reload --port 8000

# Open
# http://localhost:8000/           landing
# http://localhost:8000/challenges interview library
# http://localhost:8000/dashboard  sessions
```

Optional AI / runner:
```bash
# Local defaults
export PROMPTCODE_RUNNER=local            # or INTERVIEW_RUNNER
export PROMPTCODE_AI_PROVIDER=mock        # or INTERVIEW_AI_PROVIDER

# Production
export PROMPTCODE_RUNNER=docker
export PROMPTCODE_AI_PROVIDER=production
export PROMPTCODE_AI_API_KEY=...
export PROMPTCODE_AI_MODEL=gpt-4o-mini
export PROMPTCODE_AI_BASE_URL=https://api.openai.com/v1
# Build: docker/Dockerfile.interview-node|python → promptcode-runner-*:latest
```

Workspaces are copied under `backend/data/interview_workspaces/<session_id>/` (override with `interview_workspace_root` setting).

## Security notes

- Candidate file APIs **never** serve `SOLUTION.md`, audit files, or interviewer paths (server blocklist).
- Defend-your-code questions are parsed from `SOLUTION.md` **only after submit**, on the server.
- Test runner allowlists exact commands (`npm test`, `pytest -q`, …) — no arbitrary shell from user input.
- AI chat attaches **only** paths the candidate selects (max 6), never the whole repo.
- Session ownership: JWT user match **or** `X-Session-Token` / `owner_token`.

## Core routes

| UI | API |
|----|-----|
| `/challenges` | `GET /api/interview/challenges` |
| `/challenges/{slug}` | `GET /api/interview/challenges/{slug}` |
| Start → `/session/{id}` | `POST /api/interview/sessions` |
| Workspace files/tests/AI | `/api/interview/sessions/{id}/…` |
| `/session/{id}/report` | `POST …/submit`, `GET …/report` |
| `/dashboard` | `GET /api/interview/dashboard` |

Registry: `challenges/interview-registry.json` (metadata only; no spoilers).

## Status notes

Shipped in this hardening pass: Monaco IDE, nested explorer, starter snapshot diffs, ChallengeRunner + commandId allowlist, AI apply attribution, session_analysis signals, evidence-backed rubric, defend UX (guides hidden), dashboard aggregates, architecture doc.

## Still deferred / unsafe

- Real Docker-isolated per-session runners (`IsolatedRunner` stub; host runner is **not** production-safe)
- Rich auto-install of challenge deps before first test run
- Persistent multi-device session sync beyond owner token + optional auth
- Interviewer-only auth role gating for answer guides in stored evaluation metrics
- Deep prompt-quality ML judge (heuristics shipped; replaceable)

See `docs/interview-architecture.md` for request flow, event schema, and Docker roadmap.

## Acceptance mapping

Covered: library + filters, detail, start session, isolated snapshot, IDE layout (tree/editor/AI/terminal), events, controlled tests, mock/configurable AI, submit + rubric, report/timeline/defend, dashboard, SOLUTION isolation.

Eval platform (`challenge.json`) unchanged.
