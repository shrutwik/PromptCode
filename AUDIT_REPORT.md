# PromptCode security and stress audit

Date: 2026-10-02. Branch: `security/audit-fixes`.

Scope was the local app only. Nothing was sent to production. The live process on `127.0.0.1:8000` was probed with synthetic requests. It was started before these fixes, so live checks of admin routes still show the old behavior until that process is restarted.

## Setup

PromptCode is a practice-interview app plus an older LLM-submission scorer.

- API: FastAPI (`backend/app/main.py`), served with uvicorn.
- UI: static HTML/JS in `frontend/`, no separate frontend package.
- Database: Postgres in Docker (`localhost:5433` by default). SQLAlchemy async. Optional Supabase Postgres. Tests use SQLite. There is no client-side database rules layer; access control is in the API.
- Auth: email/password, bcrypt, HS256 JWTs from Authlib. Access tokens last 15 minutes. Refresh tokens last 30 days and rotate. HttpOnly cookies exist but are off unless `PROMPTCODE_AUTH_COOKIE_ENABLED` is set. The browser keeps tokens in `sessionStorage`.
- AI: OpenAI-compatible HTTP API (`PROMPTCODE_OPENAI_API_KEY` / `PROMPTCODE_AI_API_KEY`).
- Test runner: allowlisted `pytest` / `npm test` commands. Docker isolation is the production mode (`docker-compose.prod.yml` sets `PROMPTCODE_RUNNER=docker` and `PROMPTCODE_DEBUG=false`). A host subprocess runner exists only when `PROMPTCODE_ALLOW_UNSAFE_LOCAL_RUNNER=1`.
- Other services: Sentry (optional DSN), Prometheus `/metrics`.

Secrets live in environment variables. `.env` is not tracked. A scan of the current tree found rehearsal fixtures that look like keys but are short fake values, not live credentials. Full git history was not scanned.

## What was already in good shape

- Submission and interview session reads are scoped to the signed-in user. A mismatch returns 404.
- Profile update only accepts name and bio fields.
- Passwords require length, case, a digit, and a symbol, and reject bcrypt's 72-byte truncation.
- Auth rate limit is 10 attempts per IP per minute and is stored in the database. A local burst of bad logins returned ten `401`s and then `429`.
- Trusted proxy ranges default to localhost, so `X-Forwarded-For` is not trusted from the public internet.
- Security headers are set (CSP, `nosniff`, frame deny, referrer policy). HSTS is set when debug is off.
- CORS is an explicit origin list and rejects `*` when debug is off.
- `alg: none` JWTs are rejected by Authlib 1.6.9 and 1.6.12. Verified locally.
- The locked-down Docker test container drops all capabilities, sets `no-new-privileges`, and does not mount the Docker socket.
- Challenge commands are an allowlist. Clients cannot pass a shell string.

## Findings

### High — Candidate npm install bypassed the sandbox. Fixed.

`backend/app/services/interview/runner.py` (`restore_node_manifests`, `linux_npm_docker_argv`).

The isolated test container is locked down. Before that container starts, Node dependencies were installed with a separate `docker run` that had network access, default capabilities, and `npm` lifecycle scripts enabled. Package manifests are frozen in the file API, but code running inside a test can still rewrite them on disk. The next test run would install that rewritten manifest.

Fix: restore `package.json` and lockfiles from the session's starter snapshot, refuse the install when that snapshot is missing, and run npm with `--ignore-scripts`, dropped capabilities, `no-new-privileges`, a pid limit, a memory limit, and a read-only root. Verified by `tests/test_audit_runner_isolation.py` (no Docker daemon required).

### High — Debug mode opened internal admin routes. Fixed.

`backend/app/services/interview/beta_ops_helpers.py` `require_internal` (line 27).

`/api/interview/internal/*` lists users, disables accounts, and reads session reviews. The check treated `PROMPTCODE_DEBUG=true` as enough, with no token. The local server still running old code returned `200` for `/api/interview/internal/users` and `/internal/disk` with no token. User records from that response are not copied here.

Fix: the header `X-PromptCode-Internal-Token` must match the configured token. Placeholder tokens are rejected. Comparison uses `hmac.compare_digest`. Debug no longer bypasses it. Verified by `tests/test_private_beta_ops.py::test_internal_routes_stay_closed_when_debug_is_on`.

Restart the local server before relying on this. Set a real `PROMPTCODE_INTERVIEW_INTERNAL_TOKEN`. The example value `change-me-internal-token` is rejected on purpose.

### High — Password reset token was returned in the HTTP body in debug. Fixed.

`backend/app/api/routes/auth.py` forgot-password handler. Previously, debug responses included `reset_token` for an existing user.

Fix: the body is only the generic message. Verified by `tests/test_password_reset.py`.

Still open: `backend/app/services/password_reset.py` line 62 logs the raw token when debug is on, and there is no production mailer. Forgot-password does not email anyone. See manual actions.

### High — Disabled accounts could keep minting access tokens. Fixed.

`backend/app/api/routes/auth.py` refresh handler (account-disabled check). Login and existing access tokens already returned 403. Refresh did not check `beta_status`, so a disabled user could get a new access token until the refresh token expired (30 days).

Fix: refresh returns 403 for a disabled account and does not issue new tokens. Verified by `tests/test_private_beta_ops.py::test_disable_blocks_login_and_sessions`.

### High — Opt-in host runner inherited server secrets. Fixed.

`backend/app/services/interview/runner.py` `scrubbed_host_env` (line 131).

When `PROMPTCODE_ALLOW_UNSAFE_LOCAL_RUNNER=1`, candidate tests were started with a copy of the server environment, including API keys and the database URL.

Fix: the child process only receives an allowlist (`PATH`, `HOME`, locale, temp). Secret-like names are dropped. `PYTHONPATH` is set to the session directory. Verified by `tests/test_audit_runner_isolation.py`.

The host runner still shares the machine's filesystem, network, and CPU. Do not enable it for anyone but yourself.

### Medium — HTML catch-all could join a path outside `frontend/`. Fixed.

`backend/app/main.py` `resolve_frontend_html` (line 40) and `serve_page`.

`/{page}.html` built `FRONTEND_DIR / f"{page}.html"` and served it when the file existed. A segment containing `..` or a slash could leave the frontend directory. FastAPI usually does not put slashes in that parameter; the check is still required after URL decoding.

Fix: reject empty names, `.`, `..`, slashes, backslashes, and NUL, then require the resolved path to stay inside `frontend/`. Verified by `tests/test_audit_static_pages.py`.

### Medium — Logout left the access token valid. Fixed.

`backend/app/api/routes/auth.py` `_revoke_access_token` (line 95).

Logout revoked the refresh token only. A copied access token worked until the 15-minute expiry.

Fix: the access token presented to logout is stored in the revocation table. Verified by `tests/test_auth_security.py::test_logout_revokes_refresh_token`.

### Medium — Known vulnerable Python packages. Partially fixed.

OSV was queried for the pinned versions. `pip-audit` is not installed; this was an OSV batch query, not a full lockfile scan.

Fixed in `backend/requirements.txt`, then installed in the local venv. Auth, password-reset, static-page, and runner tests: 49 passed.

| Package | Was | Now | Why |
| --- | --- | --- | --- |
| authlib | 1.6.9 | 1.6.12 | OAuth redirect and cache issues. This app uses Authlib for JWT, not the OAuth authorization server. |
| python-multipart | 0.0.22 | 0.0.32 | Multipart and query-string denial of service. No route uses file upload. |
| pydantic-settings | 2.13.1 | 2.14.2 | Symlink read if a secrets directory is configured. This app loads `.env`, not that directory. |

Not upgraded: Starlette 0.49.3 (pulled in by FastAPI 0.120.4). OSV reports form-parsing and `Host` header issues fixed only in Starlette 1.x. This app does not define upload or form routes. Jumping FastAPI to 0.142 and Starlette to 1.7 was not done in this pass. Re-test the suite before that upgrade.

### Medium — Interview list rate limit trips before the process falls over. Not a code change.

Load was run against the already-running local server (`backend/benchmarks/audit_load.py`). It was not restarted onto this branch.

`GET /health` (all 200):

| Concurrency | Requests | p50 | p95 | p99 |
| --- | --- | --- | --- | --- |
| 1 | 10 | 0.61 ms | 17.16 ms | 17.16 ms |
| 10 | 100 | 2.93 ms | 3.54 ms | 3.90 ms |
| 25 | 250 | 7.61 ms | 9.44 ms | 9.65 ms |
| 50 | 500 | 16.01 ms | 49.80 ms | 53.52 ms |

`GET /api/interview/challenges`:

| Concurrency | Requests | Result | p50 | p95 | p99 |
| --- | --- | --- | --- | --- | --- |
| 1 | 8 | 200 | 4.93 ms | 12.45 ms | 12.45 ms |
| 10 | 80 | 200 | 13.50 ms | 130.61 ms | 205.94 ms |
| 25 | 200 | 32×200, 168×429 | 24.04 ms | 371.08 ms | 553.89 ms |

What broke first: the per-IP rate limit on the challenge list, not the process, database, or memory. No crash was observed. p99 at concurrency 1 is a tiny sample.

Not tested: database down, OpenAI timeout, a long run for leaks, N+1 under Postgres, or production-sized data. `internal_list_users` runs one count query per user (`interview.py` around line 1898). That path is now token-gated and was not load tested.

A 1MB login body was not a clean body-size test: the auth rate limit already returned 429. No global max body size was found in code.

### Low — Remaining items, not changed

- Debug logs still print the raw password-reset token (`password_reset.py` line 62).
- `/metrics` is open when debug is on and `PROMPTCODE_METRICS_TOKEN` is empty. Production compose fails closed. Confirmed on the old local process: `GET /metrics` returned 200.
- Candidate containers share the Docker network `promptcode-interview-internal`, so concurrent sessions can reach each other. They still have no route to the public internet.
- Refresh rotation is not serialized. Two overlapping refresh calls with the same token can both succeed before the revocation row commits. Not reproduced with a test.
- AI chat limits are in-memory on one process (`ai_provider.py` `check_session_ai_rate_limit`). A second web worker does not share them.
- JWT in `sessionStorage` is readable by any script that runs on the page. Cookies are available and off by default.
- CSP allows `esm.sh` and `jsdelivr.net`. A compromised script on those hosts runs in the page.
- `scripts/rehearse-restore.sh` exports a fake `sk-live...` value (19 characters). It is not a real OpenAI key. Rename it so scanners stay quiet.

## Checks that did not show a bug

- SQL is SQLAlchemy expressions, not string-built queries, in the routes reviewed.
- Workspace file reads reject `..`, absolute paths, and symlinks (`contained_file`).
- Mass assignment on `PUT /api/auth/me` is limited by `UserUpdate`.

## Manual actions

1. Restart the local API so it loads this branch. Until then, internal routes on port 8000 still use the old debug bypass.
2. Set `PROMPTCODE_INTERVIEW_INTERNAL_TOKEN` to a long random value. Do not use `change-me-internal-token`.
3. Keep `PROMPTCODE_DEBUG=false` on any shared or deployed host. Production compose already does this.
4. Keep `PROMPTCODE_ALLOW_UNSAFE_LOCAL_RUNNER` unset except on your own machine.
5. Add a real password-reset email sender. Until then, users cannot reset passwords, and debug logs are the only copy of the token.
6. Set `PROMPTCODE_METRICS_TOKEN` before exposing `/metrics`.
7. Plan a FastAPI/Starlette upgrade and re-run the backend tests. Do not only bump Starlette.
8. If this repo was ever public or a secret was pasted into git, run a history scanner (`gitleaks`) and rotate anything it finds. This audit did not do that.
9. Rotate `PROMPTCODE_JWT_SECRET` if a host runner was used while the old environment leak existed and candidate code could have read it.

## Ongoing checklist

- Run `pytest` for `tests/test_auth_security.py`, `tests/test_password_reset.py`, `tests/test_private_beta_ops.py`, `tests/test_audit_runner_isolation.py`, and `tests/test_audit_static_pages.py` when auth or the runner changes.
- Re-query OSV or install `pip-audit` when dependencies change.
- Keep production on the Docker runner, with debug off, a metrics token, and an internal token.
- Do not return reset tokens, session source, or internal diagnostics in API responses.
- After any sandbox change, confirm candidate processes cannot see `PROMPTCODE_*` secrets and cannot run package-install scripts from the session directory.










## Verified continuation — A1 reset-token logging

Finding: raw password-reset tokens appeared in debug logs.
Changes: password_reset.py removes the token from logging; test_password_reset.py adds a regression test.
Local verification: targeted regression ran, 1 passed (2026-10-02).
Clean HEAD verification: pending immediately after this item commit. Previous report claims above have not been re-verified in this continuation.
Scope: local test data only. No production calls. All other pending diffs remain outside this item.

## Verified continuation — E1 forwarded-IP spoofing

Finding: trusted proxies could use a candidate-supplied leftmost X-Forwarded-For value as the rate-limit key.
Changes: client_ip.py chooses the rightmost untrusted hop; test_backend_validation.py covers spoofing and shared limiter state.
Local verification: 10 validation tests passed. Clean HEAD verification follows this commit.
A1 clean HEAD verification: all 6 password-reset tests passed; no unrelated changes required.
Runner baseline in clean HEAD: 4 passed, 1 failed because the committed runner references the pending audit-only workspace_has_escape_link helper. Actual Docker isolation remains NOT TESTED.
