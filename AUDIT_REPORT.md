# PromptCode security and stress audit

**NO-GO for authoritative scoring.** Current verified evidence is below. Historical claims are preserved only in the superseded appendix and are not accepted as current verification.

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

## Verified continuation — B2 live host-access boundaries

PASSED for the installed Python runner image: candidate UID is non-root; /var/run/docker.sock and an outside-workspace test sentinel are absent; PROMPTCODE_* and OPENAI_API_KEY are not inherited; CapEff is zero; NoNewPrivs is 1; writing /etc is denied. Host sentinel remained unchanged. The live test ran: 1 passed in 0.82s. No real secrets or other candidate data were read. Clean B2 HEAD verification follows this test/evidence commit. Deployment backend Docker-socket/entrypoint changes remain excluded and need separate privilege review.
B1 corrected clean HEAD verification: 16 live/unit/workspace tests passed (actual completed run). The inactive-interface failure and premature prior claim remain documented above.

## Verified continuation — B3 bounded resource-abuse checks (PARTIAL / FAILED overall)

Live bounded tests actually completed: 5 passed in 9.27s, including the earlier network/host checks. PID spawning is denied with EAGAIN at the configured pids.max=32; cgroup memory.max matches the configured 128 MiB; CPU quota is 0.25 and nr_throttled increases under bounded busy work; the 64 MiB /tmp tmpfs reaches ENOSPC under at most 70 MiB of writes; a separate 64 MiB memory container dies with exit 137 rather than completing a 256 MiB allocation; 2 MiB output is clipped to 1,000 characters. Added and inspected the actual Docker local log driver retention: max-size=1m and max-file=1, compression disabled. This bounds log retention before the API decodes logs.
The first log-inspection fixture run had 4 passed/1 failed because Docker returns a new collection object on each client.containers access; retaining that collection fixed the test. No backend failure was hidden. Clean B3 HEAD verification follows this commit.
FAILED / remaining: /workspace is still a read-write host bind with no per-session storage quota. Only /tmp has an enforced disk ceiling. A host-fill attack was NOT TESTED because it would be destructive. This requires an explicit bounded execution-workspace or host-filesystem quota design before deployment.
Orphan read check after the live probes: docker ps -a with interview-runner and audit test labels returned no containers. This is actual cleanup evidence for completed probes, not proof of timeout cleanup or orphaned volume handling.
B2 clean HEAD verification: the live host-boundary test passed (1 passed in 1.20s).

## Current review checkpoint — NO-GO (latest status supersedes earlier checkpoints)

Latest implementation HEAD tested: e90292f. The clean worktree was confirmed empty with git status before running the full backend suite under FastAPI 0.142.2 / Starlette 1.7.0 in the isolated audit environment, explicit SQLite/test workspaces and mocked provider. Live local Docker audit opt-in was enabled.

**FULL suite actually ran: 391 passed, 3 failed, 1 skipped in 54.49s. Overall FAILED.** All five bounded live Docker tests passed in this full run. The sole skip is the pre-existing test_docker_integration_smoke, which has an unconditional skip=True decorator; its legacy smoke path remains NOT TESTED. The new live tests do run, and do not constitute a complete candidate session.

### Authorization boundary requiring a user answer

The three failures below are unrelated frontend contract assumptions. They cannot be made passing without changing unrelated tests or UI, both outside the current audit-hunks authorization. Stopping before modifying them follows the user's instruction to stop when an audit gate needs unrelated changes. The security-only tests do not depend on uncommitted product code.

- test_frontend_layout_contract.py::test_core_frontend_pages_have_mobile_breakpoints (line 38): scans only inline HTML for breakpoints; committed index.html links an external stylesheet containing them.
- test_frontend_layout_contract.py::test_challenge_page_defaults_to_ai_assistant_tab (line 61): matches an exact adjacent class/data-tab string; the committed active chat button has intervening accessibility attributes.
- test_frontend_starter_contract.py::test_python_starter_matches_runtime_contract (line 16): expects the Python starter embedded in HTML; it is in the committed external frontend/js/pages/challenge.js.

Proposed scope for approval: update only these three stale test assertions to read the existing linked CSS/JS and parse semantic HTML attributes. Preserve the committed UI, its behavior, and all uncommitted UI/challenge/product edits. This is an unrelated test-contract correction, not a security patch; no such edit has been made.

### Commit ledger and verification

Earlier per-item entries specify exact files/hunks and actual clean-worktree checks. This is the complete new commit ledger before the documentation checkpoint:

| Finding | Commit(s) | Result and limits |
| --- | --- | --- |
| A1 reset-token logs | c6ae0ca | Fixed; clean password-reset suite 6 passed, subsequently 10 passed after A4. |
| E1 spoofed forwarded IP | 9a91e1a | Spoofed-key fix; clean validation tests 10 passed. Shared-IP volume/load tests still NOT TESTED. |
| B5 workspace boundaries | 6cfb8fc | Traversal/symlink/control-file/byte guards and .env fix; clean unit checks 14 passed. Concurrent file races and full cross-candidate live session flows NOT TESTED. |
| D1 database hangs | e17627e | 5-second readiness/connect bounds; clean reliability checks 6 passed. Recovery/pool exhaustion/mid-request failures NOT TESTED. |
| A2 production API startup | ba93460 | Refuses unsafe mode/tokens/default JWT; clean 12 tests passed. Effective deployed worker/hosting startup is NOT TESTED. |
| A3 metrics/internal token gates | 9bbb68f | Debug bypasses closed; clean 16 token/metrics/private-beta tests passed with temporary workspace root. |
| A4 reset delivery/disable | 7efea04 | Configured SMTP TLS/timeouts or no token issuance; clean 10 tests passed. Real staging SMTP NOT TESTED. |
| A5 dependency advisories | b779d82, 648ca08 | Patched compatible pins/lock; audit-test compatibility correction verified clean with 26 passes. Current full suite still FAILED on three unrelated frontend tests. |
| B1 peer network escape | 81df263, ca27227 | Live escape reproduced and removed; corrected clean checks 16 passed. Internet/metadata/host attempts blocked and only loopback UP. Actual database target was unavailable; no production network/data accessed. |
| B2 host/privilege isolation | 5642a09 | Live Python image boundary test passed locally and in clean HEAD. Node image privilege probe NOT TESTED. |
| B3 resource/log limits | e90292f | Live CPU/PID/memory/tmpfs/output/log bounds passed in clean full run. FAILED overall: persistent /workspace host bind still has no per-session disk quota. |

### Hunks still excluded (updated)

The earlier exclusion table remains the detailed inventory. Later exceptions are limited to audit findings: config.py now includes production recognition/unsafe-runner/internal-token/SMTP fields and the effective runner field; main.py includes startup and metrics security; interview.py includes only runner-health token gating; docker-compose.prod.yml includes only production markers and Docker runner mode. Its SSL weakening, assistant settings, runner profiles, and host workspace changes remain excluded. Runner isolation, log bounds, dependency files and independent audit tests are committed. No prompt, scoring, challenge, UI, model convenience, entrypoint, Docker-socket mount or automatic context behavior was committed. Historic unverified report claims remain unstaged. No inseparable mixed hunk was included; the workspace and compose mixed hunks were edited for staging only.

### Remaining / NOT TESTED

- B3 persistent workspace disk quotas are missing. Host-filling disk abuse was not run because destructive. Need a bounded ephemeral execution workspace or enforced persistent-directory quotas.
- B4 live timeout orphan/volume cleanup; B6 scoring/test/result tampering; B7 complete live npm lifecycle/config/manifest adversarial re-verification remain incomplete. Existing manifest/lifecycle unit tests passed, but do not close those live items.
- C provider-key exposure across all browser/log/error paths, distributed per-user/session/token quotas and global kill switch/spend cap, prompt injection, outages/retries, and candidate conversation isolation were not audited to completion. The loopback hang test passed only the timeout case.
- D recovery/pools, real Docker outage integration, body/JWT/race/shutdown coverage and a complete timeout inventory remain incomplete.
- E staging restart and real ramp/load/concurrent-run cap measurement were not run in this continuation; the earlier uncommitted load claims were not imported as evidence. No new p50/p95/p99/cap recommendation is claimed.
- F deployment HTTPS/CORS/security headers configuration, auth lifecycle/throttling review, all-log PII audit, retention/deletion, migration/least-privilege checks and /health disclosure review remain incomplete. CSP/header unit tests passed in the clean full suite; that is not a deployed hosting check.
- G final candidate Docker end-to-end, history/working-tree gitleaks/trufflehog scan, pip-audit/npm audit and final re-audit remain NOT TESTED, deferred until the outstanding audit and authorization boundary are resolved. The full suite above was A5/current-commit verification, not a claim that G is complete.

### Manual actions for me (current)

1. Keep this branch out of production; review each item diff. Production API boot now fails closed for unsafe settings, but the whole system has not passed the deployment audit.
2. Set PROMPTCODE_ENVIRONMENT=production, PROMPTCODE_DEBUG=false, PROMPTCODE_RUNNER=docker; keep PROMPTCODE_ALLOW_UNSAFE_LOCAL_RUNNER unset/false. Set unique non-example JWT/internal/metrics secrets and verify effective hosting/worker environment. Rotate any secrets plausibly exposed by prior host execution/reset-token logs; a history scan is still required to determine exposure.
3. For email, set PROMPTCODE_SMTP_HOST, PORT (587 default), USERNAME/PASSWORD, PASSWORD_RESET_FROM_EMAIL and HTTPS FRONTEND_URL. Stage a test-only SMTP delivery check; without configuration reset issuance stays disabled.
4. Approve or reject the narrow stale frontend-test correction above. Choose and test a persistent workspace disk-quota strategy before users can execute code.
5. Build reviewed backend and runner images and restart staging after the remaining fixes; verify image commit/version, proxy CIDRs, TLS, headers/CORS, non-root execution and Docker-daemon privilege boundaries. The pending entrypoint/socket/SSL changes are not approved by this checkpoint.
6. Before launch, configure monitoring and alerts for auth failures, DB/Docker outages, orphan runners, queue saturation, disk use and AI spend; establish data retention/deletion, encrypted backups and a rehearsed restore. Set a reviewed rollback image and migration-compatible restoration procedure; rehearse it in staging. These operations were not performed here.

### Continuation item 1 — strict frontend contract corrections

Confirmed against committed HEAD: index links local responsive CSS, challenge links external starter JavaScript, and active chat attributes include accessibility metadata. Updated only the three stale assertions in test_frontend_layout_contract.py and test_frontend_starter_contract.py; retain breakpoint coverage for every page, exact active classes/action, unique chat tab/panel and starter runtime checks. Added accessibility relationship checks. No UI edits required. Local targeted verification: 7 passed. Clean-HEAD full-suite result pending below. Status remains NO-GO.

### Continuation item 1 clean verification / item 2 B3

5fae8e5 clean HEAD full suite: **394 passed, 0 failed, 1 skipped in 52.16s** (including five live Docker audit tests). Log: /private/tmp/audit-frontend-clean.log. Skip: legacy test_docker_integration_smoke has unconditional skipif(True); dedicated live tests ran. No unrelated edits needed.

B3 change: candidate execution copies read-only /source into a per-container /workspace tmpfs capped at 256 MiB, owned by runner UID/GID 10001. Candidate writes cannot consume the host workspace filesystem or persist between runs. Workspace memory also counts against the existing cgroup memory limit; a lower memory cap can terminate execution before the disk cap. No named volume is created. This does not establish a quota for API-uploaded persistent source/dependency installation; those paths remain a separate risk for B7/D review.

Local live verification: **11 passed in 7.65s** across live Docker and runner isolation files. Bounded fill writes at most 270 MiB, observes ENOSPC at the 256 MiB mount, confirms /source is read-only and all host source bytes unchanged. CPU/PID/memory/network/root/output tests re-ran. Initial probe command failed the command allowlist (1 failed, 5 passed); corrected the probe to use the existing allowlisted command, without expanding permissions. Clean committed verification pending. Status NO-GO.

### Continuation item 2 clean verification / item 3 socket boundary

1510b45 clean HEAD: **24 passed, 1 skipped in 7.97s**, including all six live Docker attacks and production runner contracts. Log: /private/tmp/audit-quota-clean.log. The same legacy unconditional smoke skip applies. No unrelated edits needed.

Removed the previously excluded public backend Docker socket + host-workspace mount block from the working-tree compose edits. It was never committed; remaining compose product/runner-profile settings stay excluded. Added a public-backend mount contract. Docker socket access permits privileged containers and arbitrary host mounts regardless of process UID/capability restrictions; read-only socket bind does not restrict API calls. The existing sandbox-executor remains daemon-privileged. A verified restricted execution broker or separate dedicated disposable execution host is required before deployment. Compose deployment and broker privilege restriction: NOT TESTED, not implemented. Do not enable direct socket access on the public API. Status NO-GO.

### Continuation item 3 clean verification / item 4 B4

6974fb1 clean HEAD public socket contract: **1 passed in 0.01s**. The socket mount addition remains excluded/removed; no compose deployment is claimed.

B4: runner cleanup now removes anonymous volumes as well as containers. Each runner has an execution deadline (timeout plus 30-second cleanup allowance); API startup and periodic 30-second maintenance reap only expired containers matching interview role/component/deadline labels. Active leases and unlabeled/invalid-deadline resources are preserved. Docker client calls have a 10-second transport timeout. Startup bounds its initial cleanup wait to 15 seconds; daemon failures log a generic warning. A failed cleanup remains eligible for later retry. Legacy unlabeled leftovers require manual inspection; never remove all Docker resources indiscriminately.

Local completed tests: **14 passed in 27.98s** live Docker + reliability (actual timeout, removal, no created volumes, expired crash fixture removed, active fixture preserved); **2 passed in 0.86s** reaper/lifespan checks after fixing a test-only attempt to patch a read-only engine method. Initial unit attempt: 1 passed, 1 failed. Crash is simulated by leaving a running labeled fixture with an expired lease, not by terminating a real API process. Actual API process-kill recovery is NOT TESTED. Clean committed verification pending. Status NO-GO.

### Continuation item 4 clean verification / item 5 B6 — FAILED runtime grading

ed29d47 clean HEAD: **29 passed, 1 skipped in 27.86s**, including eight live Docker tests, reaper/lifespan, reliability and production contracts. Log: /private/tmp/audit-reaper-clean.log. Same legacy skip; no unrelated changes needed.

B6 editor protection fixed: tests/, __tests__/, root test_*.py, and JS/TS .test/.spec files are now immutable through candidate/assistant file writes. Candidate implementation remains editable. Local tests: **16 passed, 1 xfailed in 0.67s** across grading/workspace boundaries. The xfail is explicitly an OPEN security failure, not a passing audit item.

Live candidate attack writes a replacement test and results.json in the ephemeral workspace, emits fake pass text, and calls os._exit(0) while pytest imports candidate code. Running its assertion with --runxfail gives **1 FAILED in 0.61s**: runner returns ok=True, exit_code=0, stdout empty (pytest captures the emitted text). Thus successful process exit alone fakes correctness without running the real assertion. Result-file writes cannot persist into the host source after B3, but process/harness trust is broken. File permissions or a signed result inside that same interpreter do not solve this. Candidate code and trusted grader require separate execution/security boundaries, or correctness must be explicitly advisory and excluded from authoritative scores. This is a blocking architecture/product decision; no rubric/prompt/challenge edits made. B6 remains FAILED. Full session/G and remaining B7/C/D/E/F are NOT TESTED to completion, deferred while this decision is unresolved. Status NO-GO.

### Continuation item 11 / decision checkpoint

- e1b7404 clean HEAD grading/workspace verification: **16 passed, 1 xfailed in 0.70s**. Log: /private/tmp/audit-grade-clean.log. The xfail reproduces the runtime grading vulnerability; B6 is FAILED, not passed. No unrelated edits required.
- Marked historical/unverified report claims SUPERSEDED at the top; retained their working-tree content for review without committing those edits.
- Renamed both fake sk-live rehearsal values to test-only-restore-provider-placeholder. Shell syntax check ran successfully. Full destructive restore rehearsal: NOT TESTED (outside this narrow fixture rename; no database wiped).
- All continuation commits were verified in clean HEAD worktrees. Excluded hunks remain: UI/challenges/prompts/rubric/product context, progress route, deployment convenience/root entrypoint, SSL weakening and unverified runner profiles. The mixed production-test file contributed only the source-read-only mount assertion. The public backend socket mount addition was removed and never committed; existing executor daemon privilege is unresolved.

Manual decision required before B6 can be closed: choose authoritative grading with a separate trusted evaluator that never shares an interpreter/security boundary with candidate code, or practice-only execution with visible test results explicitly advisory and excluded from authoritative scoring. Existing arbitrary Python/Node challenge interfaces and rubric rely on in-process test execution; changing that trust model requires a deliberate architecture/product choice. No grading/rubric behavior was silently weakened.

Still NO-GO: runtime grading integrity, verified execution broker privilege isolation, persistent source/dependency quotas, B7 live npm/Node probes, C full AI budget/isolation/outage audit, D/E recovery/atomic limiter/load/capacity, and F privacy/deployment/database review remain open. G final suite/E2E/scans/advisory audits remain NOT TESTED as final verification and must run last after those items. Prior manual hosting/secrets/backups/monitoring/rollback actions remain required. Do not deploy this branch based on the passing unit/live subset.

78fb374 clean HEAD verification completed: shell syntax, report supersession banner and both renamed fixture values verified; grading/socket subset **8 passed, 1 xfailed in 0.66s**. The xfail is the open B6 security failure. This final verification note is left unstaged for the next audit-item commit; all six item commits above have been verified independently in clean worktrees.

## Advisory execution mitigation — Option A

7f62b69 verified in clean HEAD: report appendix relocation and committed pending verification note confirmed by direct assertions. No application changes in that commit.

Execution and evaluation APIs now declare advisory=true, authoritative=false, feedback_kind=advisory_practice. Public scoring boundaries zero numeric rubric/total grades; legacy evaluation reads also remove numeric grading authority. UI labels runs and reports advisory. No candidate execution result is accepted as an authoritative score.

Python runs use a platform-supplied read-only reporter and exact server-controlled expectedTestIds inventory. Setup/call/teardown must all pass for every ID; duplicates, missing/short reports, skipped tests and zero-exit early termination fail. The expected inventory must be configured in the trusted challenge runner registry; missing inventory fails closed. Local runner and Node currently cannot satisfy this reporter contract and fail closed. Output counts are presentation only. A wrapper keeps tmpfs alive while bounded report bytes are read; timeout/removal and lease cleanup remain enforced.

**MITIGATION, NOT A FIX:** the reporter shares the candidate interpreter and its report files are writable inside the isolated run. Deliberately forged complete reports or interpreter monkeypatching can still lie. Expected-ID completeness blocks the demonstrated early-exit bypass; it does not authenticate correctness. NO-GO for authoritative scoring until the separate trusted evaluator is built and audited.

Completed local verification: **30 passed in 21.43s**, including live valid-report, short-report, early-exit and prior CPU/PID/memory/disk/network/cleanup attacks. Earlier verification attempts exposed Docker archive omission of tmpfs, then missing audit fixture inventories; those attempts failed and were corrected. Clean committed verification pending. No unrelated product edits were required for this targeted verification.

### Option A commit/verification split

5db83b3 contains advisory scoring/API/UI/reporting primitives. Clean HEAD verification: **18 passed, 1 xfailed in 1.07s**; its runtime bypass remained open because reporter integration was not staged in that commit. A staging-helper assertion stopped before runner/test integration; the shell continued and made the partial commit. Corrected this explicitly in a follow-up, including restoring original UI tag order in the index. No unrelated UI hunks were retained. The follow-up supplies runner report enforcement and converts the formerly xfailed bypass into a required passing regression. Clean follow-up verification pending; the completed local targeted run remains 30 passed.

## Trusted evaluator and restricted execution designs — Option B

06482ed clean HEAD targeted verification completed: **30 passed in 21.19s** including all live advisory/integrity/isolation probes. Log: /private/tmp/audit-report-clean.log. No unrelated hunks needed. This verifies the completeness mitigation, not authoritative correctness.

Design only: docs/audit-trusted-execution-design.md describes an evaluator outside the candidate interpreter, bounded challenge adapters, immutable source/inventory versions and signed job-bound results. It also describes a narrow fixed-flag broker on a dedicated disposable execution host. Existing sandbox-executor socket/group privileges imply full Docker-host control; a method-only socket proxy, non-root UID or read-only socket bind does not restrict that authority. Neither proposal is implemented. Owner approval is required before building either design. Estimated evaluator prototype 3–5 days, production infrastructure/verification 2–4 weeks plus challenge migration; broker 5–10 days plus disposable-host operations 3–5 days. These are planning estimates, not measured work. NO-GO for authoritative scoring.

## Persistent source and dependency quotas

69434e0 clean HEAD design review confirmed design-only/approval labels, fixed-template broker contract and effort estimates; **11 execution-feedback tests passed in 0.12s**. No broker/evaluator implementation performed.

Per-session source budget is 20 MiB / 1,000 files, with 1.5 MiB per-file limit and maximum 16 path components. Upload checks run under a cross-process flock outside candidate-visible source. Replacements account for existing bytes, and over-budget writes leave existing content unchanged. API cannot upload into node_modules/.venv/venv. Existing dependency caches have a separate pre-execution budget of 128 MiB / 20,000 files; oversized caches fail before container startup. Candidate execution remains bounded to 256 MiB tmpfs.

Removed runtime host dependency installation and prebuilt-venv copying from candidate execution. This prevents installer writes from exceeding a quota before validation. Reviewed Linux runner images or bounded prebuilt caches must supply dependencies. Unavailable dependencies fail rather than downloading into host storage. Node dependency image/cache preparation is a manual action and remains a functionality limitation; no claim of complete Node sessions yet. Budgets are per-session, not an aggregate storage admission policy; D/E and retention review must address aggregate capacity.

Local quota/workspace tests: **14 passed in 0.20s**, including concurrent overcommit, byte/file bounds, replacement accounting, dependency budget and protected paths. Clean committed verification pending. NO-GO for authoritative scoring.

## B7 — live npm attacks and Node image privilege probe

a44845e clean HEAD: **36 passed in 2.70s** across quota/workspace/advisory/grading tests. Log: /private/tmp/audit-upload-clean.log. No unrelated edits needed.

Live offline npm install used only local test-fixture dependencies in a size-limited ephemeral filesystem. Root/dependency lifecycle scripts stayed disabled with hostile project .npmrc; a rewritten manifest was restored from trusted starter and malicious .npmrc removed. CLI/environment force ignore-scripts and separate empty user/global config files. Node image probe confirmed non-root UID, zero effective capabilities, NoNewPrivs=1, no socket/secrets, read-only root and no persisted host node_modules or file changes. Completed local run: **6 passed in 0.85s**. Initial run failed because npm refuses the same /dev/null config file loaded as both user and global; corrected to a distinct empty global file. Unit expectations now reflect advisory host execution (no complete reporter => fail) and offline read-only installer arguments.

Legacy dependency-validation helper now uses source read-only plus 256 MiB tmpfs, network none, fixed UID 10001, CPU/memory/PID bounds and discarded output. Candidate runs do not invoke it or install host dependencies. Reviewed image/cache provisioning remains manual; Node complete-report support is not implemented and Node results cannot pass the advisory reporter contract yet. Online npm-registry installs are NOT TESTED and intentionally disabled during candidate execution. NO-GO for authoritative scoring and unresolved deployment privilege boundary.

## C — AI abuse, isolation and cost controls

1d22ff7 clean HEAD npm/Node verification: **6 passed in 1.36s**. Node installs were live/offline/local-fixture only, not registry downloads.

Added persistent atomic AI reservations shared across workers/restarts: global daily, user daily and session lifetime request/token/cost limits. Each reservation is all-or-nothing across scopes; concurrent requests cannot overcommit. Failed/possibly billed calls retain their reservation. Kill switch PROMPTCODE_AI_KILL_SWITCH=true rejects new calls; legacy chat/playground provider calls also reserve each HTTP attempt. Input bytes/framing/output allowance conservatively estimate tokens, maximum output is capped, and the request-size guard rejects >256,000 input bytes. Existing message/attachment bounds remain. Default ceilings: session 20 requests/200k tokens/$2, user 100/1M/$5 daily, global 1,000/10M/$20 daily, using configured worst-case token price (default $100 per million). These are conservative reservation budgets, not an invoice reconciler. Owner must set PROMPTCODE_AI_MAX_MICROS_PER_TOKEN at or above the most expensive allowed input/output rate and configure provider account billing limits; wrong pricing invalidates a spend guarantee. Counters need retention cleanup under F.

Provider transport timeout is bounded (interview default 15s, max 30s, overall two-attempt bound); 5xx gets one retry with backoff. Timeouts do not blindly retry possibly billed POSTs. Legacy chat calls also have 15s timeouts and bounded 5xx retry. Errors never return provider bodies or raw exception strings; known provider key echoes are redacted in content/model (and legacy content). Keys are authorization headers to provider only, not user message context.

Local completed verification: **16 passed in 13.89s** across AI controls/reliability, covering concurrent persistent caps, rollback, token/spend caps, restart persistence, kill switch, size rejection, fake-provider 5xx/key echoes, generic outage errors and live loopback hang. Initial payload construction failed and was fixed; one timing failure included TestClient startup, now the unchanged 12s two-request budget measures requests only. Clean committed verification pending.

Prompt-injection result: context assembly keeps explicit owned attachments as untrusted data and does not include provider keys or other-candidate markers. This is a data-boundary test, not a successful real-model jailbreak audit. System instructions are not confidential credentials. Actual paid-provider injection resistance, real billing reconciliation and complete browser/log exposure through a deployed provider are NOT TESTED (no test provider account configured). Session ownership is enforced before attachment loading; broad cross-candidate HTTP review continues in D/F. Older submission-scoring worker AI calls are outside these assistant budgets and must stay disabled for deployment until separately metered. NO-GO for authoritative scoring.

## Appendix — superseded historical audit narrative (UNVERIFIED)

The following material predates clean-HEAD verification. Its pass, load, restart and scan claims are superseded; retain only as investigation history.

Date: 2026-10-02. Branch: `security/audit-fixes`.

Scope was the local app only. Nothing was sent to production. The API on `127.0.0.1:8000` was restarted onto this branch for the second load test. After that test, it was restarted again with the normal rate limits.

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
- Auth rate limit is 10 attempts per IP per minute and is stored in the database. A local burst of bad logins returned ten `401`s and then `429`. Interview routes use a separate per-IP key (`interview:{ip}`, 120/minute). Chat and submissions are keyed by user id.
- Forwarded headers are ignored unless the TCP peer is in `PROMPTCODE_AUTH_TRUSTED_PROXY_CIDRS` (default `127.0.0.1/32` and `::1/128`).
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

Fix: the header `X-PromptCode-Internal-Token` must match the configured token. Placeholder tokens are rejected. Comparison uses `hmac.compare_digest`. Debug no longer bypasses it. Verified by `tests/test_private_beta_ops.py::test_internal_routes_stay_closed_when_debug_is_on`. After the restart, `GET /api/interview/internal/users` with no token returned 404.

Set a real `PROMPTCODE_INTERVIEW_INTERNAL_TOKEN`. The example value `change-me-internal-token` is rejected on purpose.

### High — Password reset token was returned in the HTTP body in debug. Fixed.

`backend/app/api/routes/auth.py` forgot-password handler. Previously, debug responses included `reset_token` for an existing user.

Fix: the body is only the generic message. The debug log line no longer includes the token (`password_reset.py` `notify_password_reset`). Verified by `tests/test_password_reset.py`, including `test_notify_password_reset_does_not_log_the_token`.

Still open: there is no production mailer. Forgot-password does not email anyone. See manual actions.

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

### Medium — Forwarded client IP used the spoofable leftmost hop. Fixed.

`backend/app/core/client_ip.py` `client_ip_from_request`.

Auth and interview limits are per IP. Untrusted peers ignore `X-Forwarded-For` and `X-Real-IP`. That part was already correct, and a test covers it.

When the peer is trusted, the old code used the first valid address in `X-Forwarded-For`. Caddy and nginx append the real client, so a request can arrive as `spoofed, real-client`. The spoofed value became the rate-limit key.

Fix: from a trusted peer, use the rightmost address that is not itself inside the trusted proxy ranges. If every forwarded address is a trusted proxy, fall back to the peer. Verified by `tests/test_backend_validation.py` (`test_auth_client_key_ignores_spoofed_leftmost_forwarded_for` and the existing proxy tests).

The proxy still has to append or replace the header. A proxy that forwards the client header unchanged, and does not append, cannot be distinguished from the real client.

### Medium — With the limiter raised, challenge-list latency queues on one database lock. No code change.

The process on port 8000 was restarted from this branch. For the probe only, `PROMPTCODE_INTERVIEW_RATE_LIMIT` and `PROMPTCODE_AUTH_RATE_LIMIT` were set to 1000000. The server was restarted afterward with those variables unset, so the normal limits (120/minute and 10/minute) are back.

150 sequential `GET /api/interview/challenges` calls returned 200, which confirms the raised limit was in effect. With the default 120/minute cap, the earlier probe returned 429 at 25 clients.

`GET /health` (all 200):

| Concurrency | Requests | p50 | p95 | p99 |
| --- | --- | --- | --- | --- |
| 25 | 100 | 6.97 ms | 7.97 ms | 8.12 ms |
| 50 | 200 | 15.73 ms | 17.68 ms | 18.15 ms |
| 100 | 400 | 30.16 ms | 31.92 ms | 32.50 ms |
| 200 | 600 | 43.07 ms | 157.54 ms | 161.02 ms |
| 400 | 400 | 39.60 ms | 80.75 ms | 91.54 ms |

`GET /health/ready` (database ping, all 200):

| Concurrency | Requests | p50 | p95 | p99 |
| --- | --- | --- | --- | --- |
| 25 | 100 | 20.69 ms | 25.58 ms | 30.49 ms |
| 50 | 200 | 42.08 ms | 74.35 ms | 78.46 ms |
| 100 | 400 | 78.31 ms | 88.82 ms | 94.83 ms |
| 200 | 600 | 152.11 ms | 351.97 ms | 650.72 ms |

`GET /api/interview/challenges` (all 200; one rate-limit row and advisory lock per request, same client IP):

| Concurrency | Requests | p50 | p95 | p99 |
| --- | --- | --- | --- | --- |
| 25 | 100 | 46.24 ms | 474.60 ms | 587.39 ms |
| 50 | 200 | 90.93 ms | 857.39 ms | 954.58 ms |
| 100 | 400 | 159.12 ms | 1.72 s | 1.92 s |
| 200 | 600 | 545.14 ms | 3.25 s | 3.72 s |
| 400 | 400 | 17.64 s | 18.71 s | 18.97 s |

What breaks: not the process. Health at 400 clients stayed under 100 ms p99 and returned only 200. The challenge list never returned 5xx. Requests for one IP take a Postgres advisory lock inside `enforce_rate_limit`, so they queue. At 400 clients the median wait was 17.6 seconds and the slowest call was 19.3 seconds, just under the 20 second client timeout. That is the practical break: one busy IP stalls its own challenge-list calls for tens of seconds. A second IP would use a different lock.

Not tested: a long run for leaks, N+1 under a large user table, or production-sized data. `internal_list_users` runs one count query per user (`interview.py` around line 1898). That path is token-gated and was not load tested.

No global max body size was found in code.

### Reliability

`tests/test_audit_reliability.py` has 6 tests. Together with the password-reset log test and the forwarded-IP tests, the run was 9 passed.

| Case | Result |
| --- | --- |
| Database hang on `/ready` and `/health/ready` | Returned 503 in under 12 seconds for both calls. `main.py` `_database_ready` now stops the ping after 5 seconds. New Postgres connections also use a 5 second connect timeout (`db/session.py`). A connect to `127.0.0.1:1` failed in under 3 seconds. |
| AI provider slow response | A local server that slept 2 seconds, with `PROMPTCODE_AI_TIMEOUT_SECONDS=0.4`, raised `AIProviderError` code `timeout` in under 1.5 seconds. The provider already mapped `httpx.TimeoutException` to that error. |
| Docker daemon down | `DOCKER_HOST=tcp://127.0.0.1:1`. The runner returned `error_code=docker_unavailable` in under 5 seconds and did not fall back to the host. |
| Container left behind after a test timeout | A fake container whose `wait` raised was killed and `remove` was called. When `remove` raised, the runner removed the container by name. That cleanup was already in `IsolatedRunner._run_docker_sync`. The new test locks it in. No extra cleanup code was required. |

### Low — Remaining items, not changed

- `/metrics` is open when debug is on and `PROMPTCODE_METRICS_TOKEN` is empty. Production compose fails closed. After this branch's restart, `GET /metrics` still returned 200.
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

1. Set `PROMPTCODE_INTERVIEW_INTERNAL_TOKEN` to a long random value. Do not use `change-me-internal-token`. The restarted local API already returns 404 for internal routes without that header.
2. Keep `PROMPTCODE_DEBUG=false` on any shared or deployed host. Production compose already does this.
3. Keep `PROMPTCODE_ALLOW_UNSAFE_LOCAL_RUNNER` unset except on your own machine.
4. Add a real password-reset email sender. Until then, users cannot reset passwords. The raw token is no longer logged.
5. Set `PROMPTCODE_METRICS_TOKEN` before exposing `/metrics`.
6. Plan a FastAPI/Starlette upgrade and re-run the backend tests. Do not only bump Starlette.
7. If this repo was ever public or a secret was pasted into git, run a history scanner (`gitleaks`) and rotate anything it finds. This audit did not do that.
8. Rotate `PROMPTCODE_JWT_SECRET` if a host runner was used while the old environment leak existed and candidate code could have read it.
9. Leave `PROMPTCODE_INTERVIEW_RATE_LIMIT` and `PROMPTCODE_AUTH_RATE_LIMIT` unset in production. They exist so a load test can raise the cap. The defaults are 120/minute and 10/minute.

## Ongoing checklist

- Run `pytest` for `tests/test_auth_security.py`, `tests/test_password_reset.py`, `tests/test_private_beta_ops.py`, `tests/test_audit_runner_isolation.py`, `tests/test_audit_static_pages.py`, `tests/test_audit_reliability.py`, and `tests/test_backend_validation.py` when auth, readiness, or the runner changes.
- Re-query OSV or install `pip-audit` when dependencies change.
- Keep production on the Docker runner, with debug off, a metrics token, and an internal token.
- Do not return reset tokens, session source, or internal diagnostics in API responses.
- After any sandbox change, confirm candidate processes cannot see `PROMPTCODE_*` secrets and cannot run package-install scripts from the session directory.
