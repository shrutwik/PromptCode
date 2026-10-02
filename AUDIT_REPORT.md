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

## Verified continuation — B5 candidate workspace boundaries

Finding: committed runner imported an unstaged isolation helper; API containment used an unsafe string-prefix check.
Changes: registry/workspace audit hunks enforce contained paths, reject symlinks, freeze runner controls, and cap UTF-8 file writes. A new regression caught and fixed leading-dot stripping that allowed .env writes.
Local verification: 14 workspace-boundary and runner-isolation tests passed. Clean HEAD verification follows this commit.
Excluded: automatic question context and default workspace-path convenience change. Actual non-root/container/network isolation is NOT TESTED by these unit tests; B5 remains partly open.
E1 clean HEAD verification: 10 validation tests passed without unrelated changes.

## Verified continuation — D1 bounded database readiness

Finding: a database hang could leave readiness requests waiting indefinitely; new Postgres connections lacked a connect timeout.
Changes: db/session.py sets a 5-second connect timeout; main.py bounds both readiness pings to 5 seconds. The product /progress route is excluded.
Local verification: reliability tests ran, 6 passed in 12.92s, using a loopback fake AI provider, refused local database/Docker ports, and mocked container cleanup. The first sandboxed run had 5 passes and a loopback-bind PermissionError; it was rerun with loopback permission.
Clean HEAD verification follows this commit. Database recovery, real pool exhaustion, and live-container cleanup remain NOT TESTED.
B5 clean HEAD verification: 14 workspace/runner tests passed with no unrelated changes.

## Continuation checkpoint — NO-GO for real users

Four hardening items were committed separately and verified in clean worktrees of each HEAD. These are the first four completed items. The full A–G deployment audit is ongoing under the latest user instruction to continue with remaining items.

| Item / commit | Included files and hunks | Clean HEAD tests actually run |
| --- | --- | --- |
| A1 / c6ae0ca | password_reset.py: remove raw token logging and correct delivery-hook docstring; test_password_reset.py: logging import and regression; this report: new evidence only | test_password_reset.py: 6 passed |
| E1 / 9a91e1a | client_ip.py: trusted-proxy chain selection; test_backend_validation.py: expected rightmost hop and spoofing regression; this report: new evidence only | test_backend_validation.py: 10 passed |
| B5 / 6cfb8fc | registry.py: frozen control-file recognition, including .env normalization fix; workspace.py: os/imports/byte cap, diff containment, symlink rejection, contained paths, runner helper, write validation; new test_audit_workspace_boundaries.py; this report: new evidence only | workspace-boundary and audit-runner-isolation tests: 14 passed |
| D1 / e17627e | db/session.py: connect timeout; main.py: asyncio, bounded readiness helper and both readiness callers; new test_audit_reliability.py; this report: new evidence only | test_audit_reliability.py: 6 passed in 12.97s |

Test environments used explicit test-only JWT secrets, SQLite temporary databases, mock providers or a loopback HTTP mock, refused localhost ports, and mock Docker containers. No production environment was used. The installed workspace Python environment was reused: dependency installation from a fresh lockfile was NOT TESTED. B5 does not close actual container isolation; D1 does not close recovery, request-time database failures, or pool exhaustion.

The clean baseline runner test initially failed (4 passed, 1 failed) because HEAD referenced the missing audit helper workspace_has_escape_link. Adding only the audit isolation helpers fixed it. The new boundary regression initially failed on .env writes; preserving the leading dot fixed it. No tested audit check required unrelated product changes. An initial reliability run failed to bind its loopback server under filesystem/network sandbox restrictions; rerunning with loopback permission passed. Do not interpret mocked cleanup as real-container cleanup evidence.

### Excluded and pending hunks

All exclusions remain uncommitted in the primary checkout. The original changed-file inventory is /private/tmp/promptcode-audit-changed-files.md.

| File | Hunks left out / reason |
| --- | --- |
| .github/workflows/backend-ci.yml | Runner build/push/tag/rollback additions: deployment changes, not yet verified as an audit item; no CI security scan added in this batch. |
| backend/app/api/routes/interview.py | Product progress selection, automatic question attachments/test-output context, dashboard title, and disk-root convenience changes excluded. Rate-limit override, write-error handling, edit limits, guardrails, and runner-health token gating remain pending audit review/test. |
| backend/app/schemas/interview.py | guide, challenge_title, test_output fields: product/context changes excluded. |
| backend/app/services/interview/ai_provider.py | Model/config/fallback, prompt, context, and guardrail hunks mix product and audit behavior. None staged; limits, injection protections, and error handling need an independent audit patch/test. |
| backend/app/services/interview/registry.py | No pending hunks after staging only frozen-file protection and fixing .env handling. |
| backend/app/services/interview/workspace.py | Default workspace-root path change excluded as convenience; automatic question-context constants/helpers excluded as product behavior. The mixed additions were cleanly split with add -p edit; only security helpers were staged. |
| backend/tests/test_deployment_contracts.py | Bundled-Postgres SSL-default expectation and Docker-runner assertion: deployment contract not validated; excluded. |
| backend/tests/test_interview_mvp.py | Automatic question-context import/test: product behavior excluded. |
| backend/tests/test_interview_production.py | Pending isolation/provider/guardrail tests mix audit and model/context behavior; not staged or claimed passing. New independent audit tests avoid that dependency. |
| docker-compose.prod.yml | SSL-default weakening, AI model/provider, runner/profile/workspace settings: pending deployment review and live checks; excluded. |
| docker-compose.yml | Runner services, Docker-socket and host-workspace mounts, assistant configuration: pending host-access review; excluded. A backend Docker socket requires careful privilege analysis. |
| docker/Dockerfile.backend | Dependency prebuild and entrypoint/user changes: deployment changes pending non-root verification; excluded. |
| docker/Dockerfile.interview-python | Added challenge framework dependencies: excluded; pinned versions need the dependency advisory review. |
| docker/entrypoint-backend.sh | Untracked deployment entrypoint: excluded until privilege and startup behavior are verified. |
| docs/deployment.md | Model convenience and deployment/SSL explanations: excluded pending associated implementation verification. |
| docs/pre-beta-checklist.md | Live-provider/model convenience instructions: excluded. |
| backend/app/main.py | /progress product route excluded; only readiness changes staged. |
| backend/app/core/config.py | Runner .env convenience and assistant model/provider settings excluded; production startup enforcement not implemented by these hunks. |
| backend/app/api/routes/auth.py; backend/app/core/ratelimit.py | Configurable rate-limit helper/override: pending staging load-test item; excluded from spoofing fix. |
| .env.example | Provider/model and runner convenience additions excluded. |
| AUDIT_REPORT.md | Pre-existing restart, load results, reliability, and verification claims left unstaged because this continuation did not reproduce them. Only new explicitly verified evidence entries are committed. |
| All other inventory files | Challenge, UI, scoring, prompt/level, architecture, screenshots, pitch/video, tooling artifacts: unrelated; untouched and unstaged. |

No inseparable hunk was silently included. The workspace mixed hunk was edited only for staging; its product code remains in the working tree.

### Highest-priority next work

- A2: enforce production startup refusal for debug/unsafe host runner, missing/example internal and metrics tokens, and default JWT secrets. Production recognition must be explicit and covered by boot tests.
- A3: close the debug /metrics bypass and pending runner-health debug bypass; exercise all internal routes with missing, wrong, placeholder, and valid tokens.
- A4: disable reset cleanly or configure bounded email delivery, preserving identical known/unknown-account responses. Current token-safe hook does not send mail.
- A5: jointly upgrade FastAPI/Starlette against exact current advisory versions and run the full suite. Advisory lookup and dependency scans were NOT TESTED in this batch.
- B1–B7: live Docker network/host/resource/timeout/isolation/tampering/lifecycle attacks with test-only workspaces. The unit checks cannot prove memory/CPU/PID/disk/output enforcement or prevention of fabricated scoring results.
- C: shared request/token/spend controls and provider kill switch; key/log/error review, prompt injection and candidate-data isolation, timeout/retry behavior beyond the one slow loopback response.
- D/E/F: database recovery/pool exhaustion, real Docker outages, oversized/JWT/race/shutdown behavior, staging restart/load ramps and run backpressure, deployment headers/auth/privacy/retention/migrations/health checks.
- G: full suite, Docker candidate end-to-end, history/tree secrets scan, pip-audit/npm audit, and complete re-audit remain NOT TESTED. They must run last after the remaining fixes.

### Manual actions for me — deployment remains blocked

- Do not deploy this checkpoint to real users. Keep debug and the unsafe host runner disabled on any shared environment; configure strong unique JWT, internal, metrics, and provider secrets. Production boot enforcement is still pending.
- Rotate JWT/provider/database/internal secrets if earlier host-runner execution or token logs could have exposed them; determine actual exposure before asserting a rotation is complete.
- Configure a password-reset mail provider or approve the cleanly-disabled reset behavior; no real reset email is currently sent.
- Restart local/staging only after the remaining fixes, build patched runner images, and verify the reviewed commit plus effective environment. Never reuse real candidate data in attack/load tests.
- Verify proxy trust ranges, HTTPS/HSTS/CORS/CSP, database TLS and least privilege, Docker-daemon privileges, runner network isolation, and quotas before hosting approval.
- Establish and test encrypted backups/restores, retention and deletion procedures, monitoring/alerts for unavailable dependencies, orphan runners, queue saturation, authentication failures, and provider spend.
- Prepare rollback to a reviewed image/commit and compatible migration state; rehearse restoration and rollback in staging. These operational actions have not been performed in this continuation.

## Verified continuation — A2 production startup refusal

Added a startup gate: debug-off is production; PROMPTCODE_ENVIRONMENT=production additionally catches debug-on deployments. Refuses debug, selected host runner or unsafe host opt-in, missing/example metrics/internal tokens, and default/example JWT secrets. Only security settings/startup call and production marker/Docker runner compose hunks are included; assistant config and SSL weakening remain excluded.
Local verification: 12 startup tests passed, including actual lifespan boot refusal. Clean HEAD verification follows the item commit. D1 clean HEAD tests previously ran: 6 passed in 12.97s.

## Verified continuation — A3 token-protected metrics and internal APIs

Closed the /metrics debug bypass and pending internal runner-health debug bypass. Metrics and internal checks reject missing/example configuration and compare token bytes in constant time. New tests exercise all registered internal routes with missing/wrong tokens without allowing database access, plus missing/example metrics/internal secrets and a correct metrics token. Updated existing metrics tests for the intentional production boot refusal introduced by A2.
Local verification: token gates 8 passed; metrics/private-beta checks run before commit below. Clean HEAD verification follows this commit. A2 clean HEAD: 12 startup tests passed.

## Verified continuation — A4 real reset delivery or disabled service

Configured delivery uses STARTTLS with verified TLS, a 10-second SMTP operation timeout, and a 12-second outer response bound. Configure PROMPTCODE_SMTP_HOST/PORT/USERNAME/PASSWORD, PROMPTCODE_PASSWORD_RESET_FROM_EMAIL, and PROMPTCODE_FRONTEND_URL (HTTPS outside debug). Without host/from/valid origin, forgot-password returns the same generic response for every account and issues no reset token. Delivery failures keep that response and log neither recipient, token, nor exception details. Reset emails include the existing reset-page link and single-use token.
Local verification: 10 password-reset tests passed, including disabled issuance, known/unknown responses, single-use/expiry behavior, mocked TLS/timeout mail delivery, provider configuration, and secret-free failure logging. Real SMTP delivery is NOT TESTED: no staging mail provider is configured or authorized for this run. Clean HEAD verification follows this commit.
A3 clean HEAD verification: 16 passed after setting the test workspace root to /private/tmp; the prior 14-pass/2-fail run was caused by write restrictions on the verification checkout. No unrelated code changes were required.

## Verified continuation — A5 patched FastAPI/Starlette pair

Pinned FastAPI 0.142.2 and Starlette 1.7.0 together, regenerated requirements.lock with the CI pip-compile options, and added httpx2 to development dependencies for Starlette's TestClient. Package metadata confirmed compatibility; pip check passed in a fresh temporary audit environment. The lock regeneration also reconciles previously stale direct security pins.
Exact upstream fixed versions: GHSA-86qp-5c8j-p5mr Host parsing: 1.0.1; GHSA-jp82-jpqv-5vv3 path/hostname parsing: 1.3.0; GHSA-82w8-qh3p-5jfq urlencoded form DoS: 1.3.1; GHSA-x746-7m8f-x49c HTTP method dispatch and GHSA-wqp7-x3pw-xc5r Windows UNC static-file handling: 1.1.0. Sources: https://github.com/Kludex/starlette/security/advisories (each GHSA has its own page under that URL).
Full backend suite actually ran on clean A4 source with new dependencies: 383 passed, 6 failed, 1 skipped in 49.91s. Fixed audit test assumptions for FastAPI's lazy included-router enumeration using OpenAPI paths, and made the CSP hash test use its own inline-script fixture rather than unrelated frontend code. The runner network failure is a real B1 issue. Three frontend layout/starter contract failures are unrelated and remain untouched. The full suite is FAILED, not passing. Clean A5 HEAD verification follows this commit.
A4 clean HEAD verification: 10 password-reset tests passed. Real SMTP remains NOT TESTED.
Live B1 baseline: a disposable malicious candidate reached another disposable container on the shared internal network. Internet/metadata/host probes could not connect, but an unavailable target alone does not prove isolation. The disposable victim was removed. B1 fix/re-test is next.

### A5 verification correction

Clean b779d82 targeted verification actually ran: 25 passed, 1 failed. The remaining token test counted URL paths as routes: there are 14 internal operations across 13 paths because review supports both GET and POST. Corrected the coverage assertion to count operations without reducing coverage. Local token-gate re-test: 8 passed. Clean follow-up HEAD verification follows the corrective A5 test-only commit. Full-suite failures remain explicitly open.

## Verified continuation — B1 candidate network escape

FAILED before patch: live candidate pytest code connected to a disposable HTTP peer on the shared internal Docker network (172.20.0.2:8765). Fixed candidate runs to use network_disabled=True rather than a shared network. Live re-test blocked the same peer; the automated test also checks localhost and egress attempts. Its first assertion that only lo exists failed because Docker exposes inactive tunnel devices; these devices do not imply an active route. This eliminates routing to real databases; no actual staging database was probed because none is running. A network-install phase for trusted manifests remains separate and is still subject to B7 review.
CORRECTION: that local automated run actually had 15 passed and 1 failed (overly strict interface enumeration). The earlier 16-pass claim was recorded before the running test result returned and was incorrect. Test fixtures use bounded memory/CPU/PIDs, temporary directories, no real secrets, and remove their victim container/network. Clean B1 HEAD verification follows this commit.
A5 corrective clean HEAD verification: 26 token/header/reset tests passed in 4.09s. Full backend suite remains pending re-run after network hardening, with three pre-existing frontend contract failures still open.

### B1 corrected verification

Clean 81df263 live verification failed the same inactive-interface assertion. After correcting the test to require only loopback to be UP, the local bounded live/network/runner/workspace checks actually completed: 16 passed. The fixed test still requires localhost connectivity and rejects peer, public IP, metadata, and host connections. Clean corrective HEAD verification follows its commit.
