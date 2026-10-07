# Performance work and release verification

This checkpoint extends the measured changes in [first pass](performance-first-pass.md)
and [execution pass](performance-execution-pass.md). Capacity, execution deadlines,
and candidate scoring behavior are unchanged.

## Release repairs

| Issue | Reference | Change | Verification |
|---|---|---|---|
| Lint blocked later checks; strict annotations were incomplete | `scripts.run_backend_lint`, existing ASGI and SQLAlchemy types | Mechanical import cleanup; retain model registration and fixture exports; annotate JSON payloads, cookies, middleware and database helpers | Repository lint passes; strict mypy passes for all 29 configured files |
| ORM metadata disagreed with existing migrations | Beta-operations and grading migrations | Preserve nullable JSON fields and the existing grading-session unique constraint in metadata; no migration or production data rewrite | Upgrade a fresh PostgreSQL database to head, then `alembic check`: no new operations |
| Startup rehearsal used an obsolete executor and incomplete worker settings | Production compose, execution-broker security checks, backend entrypoint | Disposable authenticated TLS broker; explicit test credentials and isolated workspace; propagate worker runner/metrics settings; skip ownership changes on read-only mounts | Real disposable Docker rehearsal: API ready, both workers healthy, ten challenges seeded, second seed unchanged |
| Workflow tests relied on developer environment and stale provider doubles | Managed workflow fixture and budget tests | Disable developer dotenv for tests; explicit mock provider and trial caps; chunk-iterable Modal output fixture; include semantic reply review; dependency mounts use a controlled fixture | Full initial local suite: 950 passed, 70 opt-in checks skipped, 77.7% coverage. Clean run exposed one provider-fixture failure, corrected and verified with 22 targeted checks; Modal suite: 28 passed; deployment/integration set: 100 passed |

The authoritative final clean Linux release run is linked from [PR #22](https://github.com/shrutwik/PromptCode/pull/22).
All six strict evaluator gates pass locally; the locked dependency audit found
no known vulnerabilities. Frontend session-state tests: 25 passed.

## Image input hygiene

Docker uploads exclude local Python/Node dependencies, persisted backend workspace
data, development SQLite databases and tool caches. The image build installs
reviewed dependencies from package/lock files. Runtime workspace directories are
initialized separately. These exclusions preserve local files while preventing
runtime candidate data from entering application image layers.

## Measurement boundaries

The public-page baseline and isolated before/after experiments remain documented
in the first two reports. The local startup rehearsal is functional verification,
not a production capacity benchmark. Deployment smoke results belong to the
completion checkpoint; do not infer authenticated editor speed, concurrent-user
capacity or production percentiles from local tests.

Collect `sandbox.complete` phase timings and `execution.admission` wait/outcomes
on the deployed revision before tuning execution capacity. Small production
smoke samples should be kept separate from capacity claims.
