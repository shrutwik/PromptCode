# Interview architecture

Additive interview simulation on the existing **FastAPI + vanilla JS + SQLAlchemy/Alembic** stack.
Eval platform (`challenge.json`, sandbox workers) is untouched.

## Request flow

1. Library → `GET /api/interview/challenges`
2. Detail → `GET /api/interview/challenges/{slug}` (README only; no SOLUTION / interviewer metadata)
3. Start → `POST /api/interview/sessions` copies challenge → per-session workspace + `.starter` snapshot
4. Workspace UI loads Monaco, nested explorer, AI chat, tests via `command_id`
5. Diff → `GET .../diff` (optional `record=true` emits `final_diff_viewed`)
6. Submit → allowlisted tests + rubric + signals; defend questions stripped of guides
7. Defend → `GET/POST .../defend` (4 questions, one-at-a-time client UX)
8. Dashboard → aggregated stats; trends only after ≥3 completed sessions

## Workspace lifecycle

```
challenges/<slug>/          # immutable source (never written by interview APIs)
backend/data/interview_workspaces/<session_id>/           # candidate working copy
backend/data/interview_workspaces/<session_id>.starter/   # immutable starter for diffs
```

Blocked from candidate file APIs: `SOLUTION.md`, `AUDIT*`, `*interviewer*`, `.reference*`.

Session workspaces are the only paths mounted into Docker runners. Source challenges,
host secrets (`.env`, API keys, DB URLs), other sessions, and Docker socket are never
mounted. `SOLUTION.md` / hidden evaluator content is excluded from workspace copies
and never sent to the AI provider.

## Challenge runner

- Interface: `ChallengeRunner` with `run_tests` / `run_targeted_tests` / `run_benchmark`
- Implementations:
  - `LocalDevelopmentRunner` — host subprocess (**dev only**, not production-safe)
  - `IsolatedRunner` — ephemeral Docker containers (**production**)
- Client sends **`commandId` / `command_id` only**; server resolves via challenge registry
  `runner.commands` + global allowlist (`npm test`, `pytest -q`, …). Arbitrary shell is rejected.
- Env: `PROMPTCODE_RUNNER=local|docker` (alias: `INTERVIEW_RUNNER`). Production must use `docker`.
  **Never silently downgrades** docker → host when the daemon/image is missing; returns a clear error.

### Docker IsolatedRunner lifecycle

1. Resolve allowlisted argv from `command_id` + registry runner config
2. Optionally copy prebuilt `node_modules` / `.venv` from challenge source if present (never `npm install` / `pip install` inside the candidate container)
3. `docker run` ephemeral container: mount **session workspace only** at `/workspace`
4. Limits: CPU 0.5–2, memory 256–1024MB, timeout 5–120s (defaults ~1.5 CPU / 768MB / 60s), PID limit, output clip
5. Network: **disabled** (`network_disabled=True`). No outbound internet; cloud metadata and internal services are unreachable. Do not enable bridge networking for candidate runs.
6. Capture stdout/stderr/exit/duration; scrub host paths; parse passed/failed/skipped when possible
7. Kill + remove container (always)

### Images

| Image | Dockerfile | Use |
|-------|------------|-----|
| `promptcode-runner-node:latest` | `docker/Dockerfile.interview-node` | TypeScript / Node / React challenges |
| `promptcode-runner-python:latest` | `docker/Dockerfile.interview-python` | Python challenges |

Registry per-challenge `runner.image` selects the image. Challenge-specific images are allowed later without API changes.

Build locally:

```bash
docker build -f docker/Dockerfile.interview-node -t promptcode-runner-node:latest .
docker build -f docker/Dockerfile.interview-python -t promptcode-runner-python:latest .
```

### Runner health (admin/internal)

`GET /api/interview/internal/runner-health` — daemon ping, image presence, simple exec probe, documented limits.
Allowed when `PROMPTCODE_DEBUG=true` or `X-PromptCode-Internal-Token` matches `PROMPTCODE_INTERVIEW_INTERNAL_TOKEN`.

## AI provider

- Interface: `AIProvider` + `AIRequest` / `AIResponse`
- Implementations: `MockAIProvider` (default/dev/tests), `ProductionAIProvider` (OpenAI-compatible HTTP)
- Env (preferred): `PROMPTCODE_AI_PROVIDER=mock|production`, `PROMPTCODE_AI_API_KEY`, `PROMPTCODE_AI_MODEL`, `PROMPTCODE_AI_BASE_URL`
- Aliases still accepted: `INTERVIEW_AI_*`, `OPENAI_API_KEY`
- Production without credentials **fails clearly** (no silent mock fallback). Keys never sent to the browser; never logged.
- Context: only candidate prompt + attached files + highlight + optional test-output note + minimal system instructions.
  **Never** SOLUTION.md, hidden evaluator, interviewer metadata, reference solutions, or trap metadata.
- Apply workflow unchanged: `accepted|modified|rejected` → attribution events. No silent mutate.
- Streaming: **not enabled** yet (non-streaming first to keep architecture risk low).
- Failures (`timeout`, `rate_limit`, `unavailable`, `auth`, `invalid`): keep `ai_prompt` event; emit `ai_provider_error`; **no scoring penalty**.
- Per-session rate limits: RPM + concurrent; context size validated with user-visible rejection (no silent attachment drops).
- Privacy: prompts/responses stored on session AI messages + timeline for review; treat as interview data, not training export. Do not put API keys in logs.

## Event schema (core)

`session_started`, `file_viewed` (deduped consecutive), `file_searched`, `file_changed` (on save: path/additions/deletions/source), `test_run` / `benchmark_run`, `test_result`, `ai_prompt`, `ai_response`, `ai_provider_error`, `ai_edit_proposed|accepted|modified|rejected`, `change_reverted`, `final_diff_viewed` (only when Review Changes opened), `submission`, `defend_answer`.

## Scoring

`session_analysis.py` → metrics + prompt heuristics + behavioral signals → `rubric.score_session` (100 pts, categories A–G with evidence). Activity volume ≠ performance. Provider infra failures are operational, not rubric inputs.

## Data separation

| Data | Candidate | Server |
|------|-----------|--------|
| Starter/workspace files | yes (blocked list) | yes |
| SOLUTION.md / guides | no | yes (post-submit defend parse) |
| Interviewer file roles | no | yes (`interviewer_file_roles`) |
| Hidden evaluator tests | not leaked in report | N/A (allowlisted suite only for MVP) |
| AI API keys | no | env only |

## Local vs production

| Concern | Local | Production |
|---------|-------|------------|
| Runner | `PROMPTCODE_RUNNER=local` | `PROMPTCODE_RUNNER=docker` |
| AI | `PROMPTCODE_AI_PROVIDER=mock` | `PROMPTCODE_AI_PROVIDER=production` + API key |
| Secrets | none required | Docker images built; AI key in env; no keys in repo |
| Network in tests | host network | container network disabled |

## Deployment notes / risks

- Prebuild challenge `node_modules` on the host (offline) if Node challenges need packages beyond the runner image toolchain; containers never install from the internet during runs.
- Docker socket remains on the **API host** only (same model as existing sandbox executor) — not inside candidate containers.
- Stronger isolation (gVisor/Firecracker/K8s jobs) can replace `IsolatedRunner` internals later without changing `command_id` APIs.
- Remaining product risks: session cleanup TTL, auth hardening, observability, beta onboarding — not runner/AI rewrites.

See also: `docs/interview-mvp.md`.
