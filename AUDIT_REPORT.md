# PromptCode beta readiness — security/audit-fixes

**Decision: NO-GO pending final verification. Authoritative scoring remains NO-GO.** Scope: local/staging, test data only. Target: small invite-only practice beta with clearly advisory scores. Full evidence: [appendix](docs/AUDIT_APPENDIX.md).

## Fixed

- Reset tokens removed from logs; generic password-reset responses, TLS email delivery or clean provider-disabled behavior.
- Production startup rejects unsafe debug/host-runner/default-secret configurations. Metrics/internal APIs require dedicated tokens; proxy-aware atomic IP/account throttles.
- Candidate runs: network disabled, non-root, read-only root/source, reduced privileges, CPU/memory/PID/output limits, 256 MiB ephemeral workspace, bounded uploads/dependencies, timeout cleanup and expired-run reaping. Npm lifecycle/manifest/.npmrc attack checks completed.
- Practice results explicitly advisory; numeric authoritative grades removed. Exact expected-test report completeness blocks demonstrated early-exit bypass. **Mitigation only:** candidate code can still forge in-process reports.
- Persistent assistant request/token/cost reservations, kill switch, bounded provider waits/retries and generic/redacted errors; owned-context isolation tests.
- Body/upload/time limits; bounded DB connection/command/pool waits and verified outage recovery. Shared execution slots/backpressure retain capacity during request cancellation. Fresh PostgreSQL migration ID mismatch corrected.

## Open / verification

- Final full suite, workflow (assistant edit visible → tests → submission), history/tree secret scans and dependency audits: **PENDING**.
- Docker-daemon privilege isolation and trusted evaluator are design-only; executor retains host-level daemon privilege. No authoritative evaluation permitted.
- Complete report inventories and compatible runner dependencies must be supplied; Node currently lacks a trusted completeness reporter. Real-provider jailbreak/billing, hosting HTTPS, existing DB upgrade/rollback, crash recovery/races and production capacity: **NOT TESTED**.
- Legacy AI judge is outside assistant budgets; disable it. Full privacy/retention/deletion and expired-counter maintenance review remains incomplete. No completed load/maximum-capacity claim. Unverified load script discarded; prior evidence and verification note preserved in appendix.

## Manual actions before invitations

- Deploy only reviewed commits; set invite-only access, Docker-only runner, debug off, strong unique JWT/internal/metrics/executor secrets, AI budget prices/caps and kill switch. Rotate any real secrets found by scans; never use example credentials.
- Run execution on a dedicated disposable host with no production credentials/data; public API must not receive a Docker socket. Review the restricted-broker design before implementation.
- Set a conservative runner cap (initially 2), identical across workers sharing the private lock directory; monitor saturation, failed cleanup, disk, DB errors and provider spending. Stop invitations if limits/cleanup fail.
- Configure HTTPS/HSTS, secure cookies, exact CORS/proxy allowlists, least-privilege runtime DB credentials, verified migrations/backups and a restore/rollback plan. Publish retention/deletion policy and provide a manual deletion contact.
- Restart from reviewed branch artifacts, perform staging smoke check, keep last known-good image/config for rollback. Do not expose unfinished legacy routes or paid judge.
