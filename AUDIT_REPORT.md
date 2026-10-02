# PromptCode — invite-only practice beta readiness

**NO-GO today, including a small invite-only beta. Authoritative scoring remains NO-GO.** Verification used clean committed worktrees, local Docker and disposable test data. Details and superseded evidence: [appendix](docs/AUDIT_APPENDIX.md).

## Fixed

- Reset-token logging, generic reset responses and provider-disabled behavior; unsafe production startup configurations rejected; protected metrics/internal APIs and atomic rate counters.
- Docker network/root/capability restrictions, bounded workspace/uploads/dependencies/output, timeout cleanup/reaping and execution backpressure; npm lifecycle/manifest protections.
- Results explicitly advisory, authoritative grades zeroed; expected-test completeness rejects early exits. **Mitigation, not a trusted evaluator:** candidate code can forge in-process reports.
- Assistant request/token/cost reservations, kill switch, bounded provider calls and owned-context checks; request/DB limits and outage handling.
- Vulnerable Python/npm dependencies patched; reproducible Python runner built from audited lock. Workspace authentication now refreshes/retries once; submission wording says advisory feedback.

## Verification and open issues

- Latest clean code suite: **453 passed, 0 failed, 1 skipped** (84.06s). Skip: permanently disabled legacy Docker smoke; dedicated live Docker tests ran. Earlier run: **452 passed, 1 failed, 1 skipped**; memory attack was rejected but unexpectedly reported exit 0 rather than 137. **Unresolved intermittent result; not a consistent memory-containment pass.**
- Browser/Docker workflow completed: signup, assistant proposal accepted and present in editor, 4/4 tests, submission, advisory report (`authoritative=false`, score 0), no remaining runner containers. Local HTTP provider stub only; real-provider behavior/billing **NOT TESTED**.
- pip-audit: zero known vulnerabilities in backend lock and installed Python runner. npm audit: zero in each of six challenge locks. Gitleaks: tree six findings (one actual credential in ignored local `.env`, five fixtures); history five deterministic fixtures. **Raw scans are not clean passes.**
- Open: executor Docker-daemon host privilege; Node completeness reporter/runtime workflow; production capacity/load, hosting controls, existing DB upgrade/rollback, complete privacy/deletion review and other unfinished reliability checks. **NOT TESTED / incomplete**, with earlier evidence in appendix. Unverified load script discarded; verification note committed in appendix.

## Manual actions before invitations

- Rotate local provider credential; set unique JWT/internal/metrics/executor secrets, debug off, Docker-only execution, invite access, exact proxy/CORS allowlists and configured AI prices/caps/kill switch. Disable legacy AI judge outside assistant budgets.
- Use a dedicated disposable execution host with no production credentials/data. Public API must not receive Docker socket access. Restricted broker and trusted evaluator remain design-only, awaiting approval.
- Resolve memory-test inconsistency; provide verified Node reporting or restrict supported tickets. Verify hosting HTTPS/HSTS, least-privilege DB access, migrations, backups/restore and rollback.
- Publish retention/deletion policy and contact. Start runner cap at 2; monitor saturation, cleanup, disk/DB errors and spending. Restart reviewed artifacts, smoke-test staging and preserve last known-good image/config. No merge performed.
