# Deployment (beta)

## Environments

| Env | Debug | Runner | AI | Cookies | CORS |
|-----|-------|--------|----|---------|------|
| development | `PROMPTCODE_DEBUG=true` | `PROMPTCODE_RUNNER=local` (or docker) | mock or real key | cookies optional | localhost origins OK |
| test | true | local | mock | off | test client |
| production | **false** | `docker` | real `DEEPSEEK_API_KEY` | set `PROMPTCODE_AUTH_COOKIE_ENABLED=true` | explicit origins only (no `*`) |

## Required production env

- `PROMPTCODE_DEBUG=false`
- `PROMPTCODE_JWT_SECRET` — long random, not a placeholder
- `PROMPTCODE_DATABASE_URL` — Postgres (`postgresql+asyncpg://…`), not the local default
- `DOMAIN` — public hostname (not localhost)
- `DEEPSEEK_API_KEY` — real DeepSeek key, shared by assistant and evaluation
- `PROMPTCODE_AI_PROVIDER=deepseek` — live assistant; `mock` keeps scripted replies
- `PROMPTCODE_AI_MODEL=deepseek-flash` — bounded session Q&A; production pins evaluation to the same model.
- `PROMPTCODE_CORS_ORIGINS` — comma-separated frontend origins
- `PROMPTCODE_FRONTEND_URL` — optional canonical UI URL
- `PROMPTCODE_SESSION_TTL_HOURS` — default 24
- `PROMPTCODE_MAX_RUNNERS` — interview Docker concurrency (default 4)
- `PROMPTCODE_MAX_RUNNER_WAITERS` — bounded FIFO execution backlog (default 32); beyond it admission fails closed with 503 + `Retry-After`
- `PROMPTCODE_PROBE_CONCURRENCY` — grading probes run in parallel inside one execution slot (default 2)
- `PROMPTCODE_MAX_RUNNERS_ACQUIRE_TIMEOUT_SECONDS` — per-request wait bound for an execution slot (default 15)
- `PROMPTCODE_DATABASE_POOL_SIZE` / `PROMPTCODE_DATABASE_MAX_OVERFLOW` — connections per process block (defaults 20 + 10); size against the database's `max_connections` across every API and worker process
- `PROMPTCODE_DATABASE_COMMAND_TIMEOUT_SECONDS` — per-statement cap (default 30); startup validation requires it to exceed `PROMPTCODE_DATABASE_POOL_TIMEOUT_SECONDS`
- `PROMPTCODE_INTERVIEW_INTERNAL_TOKEN` — protects `/api/interview/internal/*`
- `PROMPTCODE_METRICS_TOKEN` — required for `/metrics` when not debug

## Storage accounting

Retained interview artifacts are tracked by an incremental SQLite ledger at
`<artifact root>/.storage-ledger.db` (WAL mode). Capacity admission is O(one
workspace) instead of a full artifact-root walk, and the API no longer holds the
host-wide storage lock across the copy or write.

- The application and every worker **must** share the artifact root, exactly as
  they already must for `.submitted` and `.storage.lock`.
- The ledger is derived state. Workers reconcile it from the filesystem every 15
  minutes, `cleanup` reconciles at the end of every sweep, and
  `python -m scripts.cleanup_interview_sessions` remains the manual equivalent.
- Deleting `.storage-ledger.db` is safe: it is rebuilt from disk on the next
  reconciliation or first write. Deleting it does **not** delete candidate data.
- `python -m scripts.benchmark_storage_accounting` measures admission cost on a
  disposable tree.

## Startup

```bash
# migrate
cd backend && alembic upgrade head

# run (example)
uvicorn app.main:app --host 0.0.0.0 --port 8000
# or: python scripts/run_with_migrations.py
```

Docker app image: `docker/Dockerfile.backend`. Compose: `docker-compose.yml` / `docker-compose.prod.yml`.

Interview runner images are built in CI and tagged `promptcode-runner-node:latest` and `promptcode-runner-python:latest` on the host. Production compose sets `PROMPTCODE_RUNNER=docker`. The bundled Postgres service has no TLS, so `PROMPTCODE_DATABASE_SSL_REQUIRE` defaults to false. Set it true only when `PROMPTCODE_DATABASE_URL` points at a host that requires SSL.

Local image build, if you are not using the deploy job:

- `docker/Dockerfile.interview-node` → `promptcode-runner-node:latest`
- `docker/Dockerfile.interview-python` → `promptcode-runner-python:latest`

## Health

- `GET /health` — liveness
- `GET /health/ready` (alias `/ready`) — DB + runner config + optional sandbox executor. Does **not** run challenges. AI failure does not take the site offline.

## Cleanup

```bash
python backend/scripts/cleanup_interview_sessions.py
```

Expires due sessions, removes expired/failed/orphan workspaces, removes stopped PromptCode interview containers (`promptcode.role=interview-runner`).

## Auth note for operators

Beta default remains **Bearer access tokens** in `sessionStorage` (migrated off `localStorage`) because the vanilla SPA already depends on them. Enable `PROMPTCODE_AUTH_COOKIE_ENABLED=true` for HttpOnly `pc_access_token` / `pc_refresh_token` cookies (Secure + SameSite in prod). Prefer cookies for production beta hosts.

## Docker socket sensitivity

The production sandbox executor needs Docker access; the public backend delegates execution to it and has no Docker socket. Treat the Docker socket as **highly privileged**. Use dedicated beta infra. Never expose the Docker socket or daemon to candidates or public networks.

## HTTPS / proxy

Put Caddy or nginx in front. Terminate TLS on the public hostname (`DOMAIN`). Forward `X-Forwarded-For` / `X-Forwarded-Proto`. Restrict `PROMPTCODE_CORS_ORIGINS` to real frontend origins. Prefer `PROMPTCODE_AUTH_COOKIE_ENABLED=true` with Secure cookies behind HTTPS.

## Backups

Prefer managed Postgres backups when available. Otherwise daily `scripts/backup-db.sh` (pg_dump + gzip, 7-day retention). Restore rehearsal before private beta. Never run destructive migrations on startup — always `alembic upgrade head` explicitly (see `docs/release-checklist.md`).

## Version identity

Set `PROMPTCODE_APP_VERSION` and `PROMPTCODE_GIT_SHA` (or `GIT_SHA`). Surfaced in `/api/interview/internal/diagnostics` and feedback meta.

## DeepSeek $5 trial

For submitted-source grading, reviewer setup, calibration and failed-job recovery,
follow [grading operations](grading-operations.md). Reviewed ratings remain off
until real pilot data and independent deployment audits satisfy the release gates.

Production pins the assistant, both evaluation workers and the execution relay to
`deepseek-flash` at `https://api.deepseek.com`. Legacy challenge code requesting
an allowed OpenAI model is mapped to Flash by the relay. Legacy provider keys are
never reused for DeepSeek. Signup is open; no invite code is required.

All application-paid assistant, judge and relay calls reserve the same persistent
budget before contacting the provider. Default caps are $5 for the entire trial,
$1 per UTC day globally, $1 per user/day, and $0.50 per question or evaluation
session. The trial counter does not reset daily. These are conservative
reservations, not invoices: UTF-8 input bytes plus framing and bounded output are
charged at 2 USD micros per token. Failures retain reservations, so the app may
stop while the provider still has credit. Rates assume Flash; review them before
changing providers/models. A failed reservation prevents the upstream call.

The request caps are 200/day globally, 20/user/day and 10/question or evaluation
session. Grading and execution-relay calls share the user/global caps with hints.
A grading job can stop when its budget is exhausted. Assistant questions are
limited to 2,000 characters; the complete context is limited to 18,000 characters
(approximately 6,000 English tokens, not an exact tokenizer count), including
instructions, code and test output. Oversized context is rejected. Hint output is
limited to 600 tokens, thinking is disabled, and assistant requests do not retry
or auto-continue. Judges use their existing bounded output limits and no hidden
SDK retries. Local off-topic refusals make no provider call.

Set `PROMPTCODE_AI_KILL_SWITCH=true` in the host environment and recreate backend,
worker, worker-b and sandbox-executor to stop new paid calls everywhere. Calls
already in flight may finish. Keep the budget table across deployments/restarts;
deleting it would reset the trial reservation history. A separate account/key for
this application makes provider billing easier to compare against reservations.

### Get the key and add funds

1. Sign in or register at https://platform.deepseek.com/.
2. Open the API keys section (https://platform.deepseek.com/api_keys), create a
   key named `PromptCode beta`, and copy it when shown.
3. Open billing/top-up (https://platform.deepseek.com/top_up) and add $5 if that
   amount is offered by your account/payment method. Do not enable automatic
   replenishment for this trial. Check the dashboard's credited balance.
4. Put the key in the existing project `.env` as `DEEPSEEK_API_KEY=...`. Put it in
   the deployment server's environment too when deploying. Leave frontend files
   and public client configuration free of the key. Keep `.env` out of Git.
5. The model/endpoints and budget settings are already configured. Restart the
   app/services after updating the key; settings are cached in running processes.

Provider references: https://api-docs.deepseek.com/quick_start/pricing/ and
https://api-docs.deepseek.com/api/get-user-balance/.

### Validate credentials without paid inference

From the repository root:

```sh
PYTHONPATH=backend .venv/bin/python -m scripts.check_deepseek
```

In a deployed Compose service:

```sh
docker compose -f docker-compose.yml -f docker-compose.prod.yml exec backend python -m scripts.check_deepseek
```

The checker uses only GET balance/models requests and never prints the key.
401 means authentication failed. An unavailable balance means a top-up is needed.
It verifies key/balance/model availability, not generation quality or latency.
DeepSeek rejects paid calls with HTTP 402 when balance is exhausted.

### Prepare execution and smoke-test

Rebuild both runner images from the changed Dockerfiles. They contain the reporter;
Node also contains locked dependencies for each registered challenge. Candidate
runs have no network and perform no package installation.

```sh
docker build -f docker/Dockerfile.interview-node -t promptcode-runner-node:latest .
docker build -f docker/Dockerfile.interview-python -t promptcode-runner-python:latest .
```

The public backend delegates test runs to `/v1/interview/run` on the authenticated
executor. The request contains only a session UUID and an allowlisted command ID.
The executor loads the session from the database and derives the workspace,
command and image from the registered challenge. Both services mount the same
`PROMPTCODE_INTERVIEW_HOST_WORKDIR` path, default
`/var/promptcode/interview_workspaces`. Prepare that directory on the server and
make it writable by the backend image's `promptcode` UID/GID before startup.
Only the executor receives the Docker socket. Expired-container cleanup runs
there on startup and every 30 seconds.

Build/deploy a backend image containing these changes using your existing release
workflow, apply migrations including `audit01_ai_budgets`, then check readiness.
The hosting destination and public domain still need to be selected.

Smoke-test with a real account: signup → open question → request one hint → edit
a file → run tests → submit → answer defend questions. Check that an unrelated
question gets a local refusal. A $5 top-up does not substitute for this real-key
smoke test. The automated provider tests use mocked HTTP responses; actual key
acceptance, provider latency and production host permissions remain to be checked.

Practice execution remains advisory. The existing safety rules do not turn a
green candidate process into an authoritative grade; a missing trusted test
inventory can produce `incomplete_test_report`. Do not advertise ranked or
authoritative correctness until the trusted evaluator described in
`docs/audit-trusted-execution-design.md` is implemented.
