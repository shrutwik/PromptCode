# Deployment (beta)

## Environments

| Env | Debug | Runner | AI | Cookies | CORS |
|-----|-------|--------|----|---------|------|
| development | `PROMPTCODE_DEBUG=true` | `PROMPTCODE_RUNNER=local` (or docker) | mock or real key | cookies optional | localhost origins OK |
| test | true | local | mock | off | test client |
| production | **false** | `docker` recommended | real `PROMPTCODE_OPENAI_API_KEY` | set `PROMPTCODE_AUTH_COOKIE_ENABLED=true` | explicit origins only (no `*`) |

## Required production env

- `PROMPTCODE_DEBUG=false`
- `PROMPTCODE_JWT_SECRET` — long random, not a placeholder
- `PROMPTCODE_DATABASE_URL` — Postgres (`postgresql+asyncpg://…`), not the local default
- `DOMAIN` — public hostname (not localhost)
- `PROMPTCODE_OPENAI_API_KEY` — real key
- `PROMPTCODE_CORS_ORIGINS` — comma-separated frontend origins
- `PROMPTCODE_FRONTEND_URL` — optional canonical UI URL
- `PROMPTCODE_SESSION_TTL_HOURS` — default 24
- `PROMPTCODE_MAX_RUNNERS` — interview Docker concurrency (default 4)
- `PROMPTCODE_INTERVIEW_INTERNAL_TOKEN` — protects `/api/interview/internal/*`
- `PROMPTCODE_METRICS_TOKEN` — required for `/metrics` when not debug

## Startup

```bash
# migrate
cd backend && alembic upgrade head

# run (example)
uvicorn app.main:app --host 0.0.0.0 --port 8000
# or: python scripts/run_with_migrations.py
```

Docker app image: `docker/Dockerfile.backend`. Compose: `docker-compose.yml` / `docker-compose.prod.yml`.

Interview runner images (build before `PROMPTCODE_RUNNER=docker`):

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

The API host that runs `IsolatedRunner` needs Docker access. Treat the Docker socket as **highly privileged**. Use dedicated beta infra. Never expose the Docker socket or daemon to candidates or public networks.

## HTTPS / proxy

Put Caddy or nginx in front. Terminate TLS on the public hostname (`DOMAIN`). Forward `X-Forwarded-For` / `X-Forwarded-Proto`. Restrict `PROMPTCODE_CORS_ORIGINS` to real frontend origins. Prefer `PROMPTCODE_AUTH_COOKIE_ENABLED=true` with Secure cookies behind HTTPS.

## Backups

Prefer managed Postgres backups when available. Otherwise daily `scripts/backup-db.sh` (pg_dump + gzip, 7-day retention). Restore rehearsal before private beta. Never run destructive migrations on startup — always `alembic upgrade head` explicitly (see `docs/release-checklist.md`).

## Version identity

Set `PROMPTCODE_APP_VERSION` and `PROMPTCODE_GIT_SHA` (or `GIT_SHA`). Surfaced in `/api/interview/internal/diagnostics` and feedback meta.
