# Staged refactor verification (local)

Status: **implemented and locally verified for the stages below.** Nothing here is
a production-capacity claim. Every measurement was taken on one shared developer
machine with paid AI disabled; no hosted environment exists yet.

## 1. What was implemented

| Stage | Change | Files |
| --- | --- | --- |
| 1 — boundaries | Architecture proposal + ownership/dependency rules; executable boundary tests; hermetic test runner that stops reading the developer `.env`; test artifact-root isolation | `docs/architecture-refactor-plan.md`, `tests/test_architecture_boundaries.py`, `scripts/run_test_suite.py`, `tests/conftest.py` |
| 2 — canonicalization | Documented canonical vs legacy implementations and the paid-AI choke point; **budget/kill switch now precedes credentials on both legacy judges**; the broker's credential-free invariant is asserted by a test instead of prose | `docs/architecture-refactor-plan.md`, `services/evaluation/ai_judge.py`, `services/evaluation/prompt_quality.py`, `tests/test_architecture_boundaries.py` |
| 3 — bottlenecks | Incremental storage ledger replacing per-write full-root scans; bounded FIFO execution admission replacing instant shedding; grading-claim sweeps predicated; durable job indexes; DB timeout/pool budgets made configurable and validated | `app/services/interview/storage_ledger.py` (new), `workspace_quota.py`, `workspace.py`, `snapshot.py`, `cleanup.py`, `app/core/capacity_queue.py` (new), `app/execution_broker.py`, `app/workers/interview_grading.py`, `app/workers/queue.py`, `app/db/session.py`, `app/core/config.py`, `app/core/metrics.py`, `alembic/versions/audit04_job_queue_indexes.py` (new) |
| 3b — candidate accounting | Candidate containers no longer receive a writable telemetry mount; usage comes from the application relay that was billed. Closes the prompt-quality/telemetry forgery path | `services/sandbox/runner.py`, `services/sandbox/relay.py`, `tests/test_sandbox_telemetry_trust.py` (new) |
| 4 — verification harness | The capacity harness now computes and enforces readiness gates instead of hardcoding `capacity_validated: false` and exiting 0 despite runaway shedding | `benchmarks/interview_load.py` |
| 5 — removal | **Not done.** No legacy path was removed; each still has callers and its replacement has not been verified end to end. | — |
| 6 — documentation and operations | This file, the plan, capacity-gate docs, deployment/ops docs; alert transport added and wired into health/backup/deploy; disk-reserve and per-worker heartbeat health gates; pre-migration backup added to the deploy workflow | `docs/*`, `scripts/notify-alert.sh` (new), `scripts/check-prod-health.sh`, `scripts/backup-db.sh`, `.github/workflows/backend-ci.yml`, `.env.example`, `tests/test_alert_transport.py` (new) |

## 2. Measured effect of the storage change

`python -m scripts.benchmark_storage_accounting` builds a disposable artifact tree
and times the previous admission path (`retained_bytes(root)` under the host-wide
`.storage.lock`) against the ledger path (reserve + measure one workspace +
atomic record). Writes only under a temporary directory.

| Tree | Previous (full-root scan under lock) | Ledger path | Speedup |
| --- | --- | --- | --- |
| 200 sessions, 6.3 MiB | p50 21.11 ms, p95 22.16 ms | p50 0.58 ms, p95 1.35 ms | 36x |
| 500 sessions, 62.5 MiB | p50 53.41 ms, p95 57.57 ms | p50 0.55 ms, p95 0.61 ms | 97x |

The previous path is O(total retained bytes) and serialized across every API
process and worker; the ledger path is O(one workspace) and does not grow with the
artifact root. **Extrapolation, not measurement:** the repository's own long-lived
workspace root currently holds 463 children / 25,429 entries / 630 MB, where the
previous per-save cost is ~10x the largest measured row above. That large tree was
deliberately not used for the benchmark because it contains local candidate data.

The old code path also held the global lock across the entire copy/write. The
ledger's critical section is a single SQLite transaction.

## 2b. Capacity rehearsal re-run (same host, same bounds)

Re-run on this machine with Docker available, using the diagnostic bounds the
earlier baseline used (`--max-throttle-rate 0.5 --capacity-retries 20`) so the
comparison is like for like. Raw reports:
[before](capacity-local-results.json), [after](capacity-local-after-diagnostic.json).

| Metric (p95 ms) | 50 before | 50 after | 100 before | 100 after |
| --- | ---: | ---: | ---: | ---: |
| Workflows completed | 50/50 | 50/50 | 100/100 | 100/100 |
| Stage duration (s) | 63.06 | 65.29 | 132.13 | 131.38 |
| Source **save** | 3578 | **988** | 7434 | **2218** |
| **Submit** | 572 | 792 | 8409 | **2013** |
| Session **start** | 10512 | 12008 | 28782 | **25237** |
| Report | 147 | 192 | 146 | 300 |
| Advisory run | 1336 | 3491 | 3183 | 3318 |
| Grading queue wait | 21034 | 22598 | 51366 | 50437 |
| Grading job completion | 23075 | 24637 | 53403 | 52289 |
| Advisory shed rate | 80.3% | 75.2% | 84.1% | 86.0% |
| Unexpected HTTP errors | 0 | 0 | 0 | 0 |

**What improved.** Source save p95 fell 72% at 50 users and 70% at 100 users, and
submit p95 fell 76% at 100 users. Both match the two changes aimed at them: the
incremental ledger removed the full artifact-root walk (and the host-wide lock
around it), and the read paths stopped taking write locks. Session start also
improved 12% at 100 users.

**What did not.** The advisory shed rate is essentially unchanged (80.3% → 75.2%
at 50; 84.1% → 86.0% at 100), as are grading queue wait and job completion. This is
a capacity fact, not a policy bug: four execution slots at roughly 12 s per
advisory run can serve about 0.33 runs/second, while 100 users issue ~780 attempts
including retries. Bounded queueing plus the harness's own retries let all 150
workflows finish, but it cannot change the drain rate. Session start remains
~25-29 s because it is dominated by workspace creation and the same execution
queue. Raising `PROMPTCODE_MAX_RUNNERS` is the lever, and it must be chosen from
measured host CPU/memory, not from this number.

**Single-run caveat.** One run per configuration on a shared developer machine.
Session-start moved in opposite directions at the two stages, which is consistent
with run-to-run variance at this scale rather than a real regression. The save and
submit reductions are large enough to be well outside that noise, but they are not
a production claim.

`capacity_validated` remains **false**: latency acceptance and deployed resource
headroom are still unassessed, and the 25% shed gate fails. The strict exit path
(`--require-readiness-gates`, loaded-runner only) reports this as a failure by
design.

## 3. Execution admission

`CapacityQueue` replaces instant rejection with bounded FIFO waiting:

- `PROMPTCODE_MAX_RUNNERS` (default 4) — concurrent executions, unchanged.
- `PROMPTCODE_MAX_RUNNER_WAITERS` (default 32) — hard backlog cap; beyond it the
  broker fails closed with 503 + `Retry-After`.
- `PROMPTCODE_MAX_RUNNERS_ACQUIRE_TIMEOUT_SECONDS` (default 15) — per-request wait
  bound, now actually enforced (previously a validated-but-unused knob).
- `/ready` reports `active` and `waiting`.

Locally verified by `tests/test_execution_broker.py`: a saturated host admits a
queued caller as soon as a slot frees; a full backlog refuses with a retry hint;
cancellation still keeps the slot until the worker thread stops.

**Not verified:** the effect on the 50/100-user rehearsal, because that run
requires Docker and rebuilds the runner images. The measured 80-84% shed rate
should fall once callers wait instead of retrying, but that is an expectation, not
a measurement. Frontend still has no 429/503/`Retry-After` handling or explicit
queued state (see remaining work).

## 4. Baselines and test results

Hermetic baseline command (does not read the developer `.env`, matching CI):

```sh
cd backend
PROMPTCODE_JWT_SECRET=ci-test-secret PROMPTCODE_DEBUG=true \
  ../.venv/bin/python -m scripts.run_test_suite tests -q \
  --ignore=tests/test_audit_live_docker.py
```

| Run | Result |
| --- | --- |
| Baseline before changes | 705 passed, 8 failed, 59 skipped |
| Final | **752 passed, 0 failed, 50 skipped** |

The eight baseline failures were each resolved rather than excused:

| Failure | Cause | Resolution |
| --- | --- | --- |
| `test_config_security.py` (4) | A local `.env` pinning DeepSeek triggers the legacy-key substitution; the tests assert on the resulting error text | The hermetic runner now disables the repository `env_file`, matching CI, so the tests see the configuration they were written for |
| `test_shared_ai_budget.py::test_judges_cannot_reach_provider_after_budget_denial` | The legacy judge checked credentials before reserving budget | Budget/kill switch now precedes credentials on both legacy judges |
| `test_prompt_quality_models.py` (2) | Same ordering issue | Reservation hoisted out of the model retry loop; `HTTPException` added to the fallback errors |
| `test_password_reset.py` (3, counted within the above) | Production startup validation depends on the host's Docker socket | Tests made host-independent, matching the existing startup-security suite |
| `test_metrics.py::…non_debug_mode` | Depended on a signing key from the caller's environment | The test now supplies its own production configuration |
| `test_private_beta_ops.py::test_scoring_version_on_submit` | Asserted a literal `"v2"` after scoring moved to the evidence-based v3 | Asserts the canonical `SCORING_VERSION` constant so it cannot drift again |

Totals shifted slightly because four live-tier tests are now excluded from this
count and run separately below, and the new tests in this work are included.

The documented `pytest -q` command still works, but on a machine with a populated
`.env` it exercises a different configuration than CI. Use
`python -m scripts.run_test_suite tests -q` for a CI-equivalent run; the runner also
forces a deterministic exit so a FastAPI lifespan task cannot hang interpreter
shutdown.

### Live infrastructure tier (Docker + PostgreSQL)

The audit's largest verification gap was that all real-infrastructure coverage was
opt-in and never executed, so real container isolation, real Postgres locking and
the populated-database migration path were unproven. That tier now runs green:

```sh
cd backend
PROMPTCODE_AUDIT_DOCKER=1 PROMPTCODE_JWT_SECRET=ci-test-secret PROMPTCODE_DEBUG=true \
  ../.venv/bin/python -m pytest \
  tests/test_audit_live_docker.py tests/test_audit_live_database.py tests/test_audit_live_npm.py \
  tests/test_audit_live_migrations.py tests/test_grading_live_database.py tests/test_legacy_broker_live.py \
  tests/test_trusted_evaluator.py tests/test_interview_executor.py \
  tests/test_audit_grading_integrity.py tests/test_audit_runner_capacity.py -q
```

Result: **107 passed** (108.8 s). This executed, against disposable containers on
this host: real candidate-container isolation, network and capability boundaries,
ENOSPC behaviour, PostgreSQL outage/recovery/pool exhaustion, real grading
lease/admission/locking concurrency, the broker/SDK relay integration, and the
migration tests below. Two tests in this tier failed before this work because my
own execution-queue refactor retired the `_active` counter they patched; both are
fixed in `tests/test_legacy_broker_live.py`.

**Populated-database migrations (new).** `tests/test_audit_live_migrations.py`
provisions a disposable PostgreSQL, builds the schema at the revision *before* the
newest one, seeds a user, a submitted session and a grading job, then upgrades to
head and asserts every row survives and `alembic_version` equals the repository
head. It also asserts the four new queue indexes exist and that the newest revision
downgrades and reapplies without touching rows. This closes the audit's
highest-severity operations gap: migrations were previously only exercised on an
*empty* database.

**Still not reversible:** older revisions, notably `9fb7f8d6f3b1`, which deletes
duplicate leaderboard rows before adding uniqueness. A downgrade past it loses
those rows permanently; the new test records that limitation rather than hiding it.

### Migration validation

`alembic upgrade head` was applied to a throwaway SQLite database, then
`downgrade audit03_interview_grading` and `upgrade head` again, confirming
`audit04_job_queue_indexes` is reversible and leaves no index behind. The chain has
a single head. The Postgres path was **not** run (no local Postgres in this session);
CI's default suite does not exercise it either.

### Lint / type checks

- `python -m scripts.run_backend_lint`: 156 errors before this work, 142 after
  (the remaining ones are pre-existing import-organization and typing findings in
  untouched modules).
- `mypy --strict` on `app/core/` and `app/api/`: 97 pre-existing errors, none in
  the new modules; `app/core/capacity_queue.py` and
  `app/services/interview/storage_ledger.py` type-check clean.

## 5. Behaviour deliberately preserved

- Authorization, API routes and response shapes are unchanged. `check_upload`
  still raises the same `ValueError("Session source quota exceeded")`; a denied
  capacity reservation still raises HTTP 507 with `Retry-After: 60`.
- Immutable submissions are still content-addressed, re-verified and written before
  the grading job row is committed. Review/appeal history is still append-only.
- The ledger is derived: `cleanup` forgets deleted entries and then reconciles, and
  workers reconcile every 15 minutes. `.submitted` snapshots are never deleted by
  this work.
- The `$5` AI trial budget and every existing AI cap are untouched. **No paid
  provider call was made during this work.**

## 5b. Candidate accounting and alerting

**Telemetry trust.** `_build_container_run_kwargs` no longer mounts a writable
telemetry directory, and the success path returns `relay.recorded_calls()` — the
application process that actually made the billed provider call — instead of
reading `calls.jsonl` from the container. A candidate can no longer influence
token, cost or prompt-quality inputs. Covered by
`tests/test_sandbox_telemetry_trust.py`; the broker path already behaved this way.

**Alerting.** `scripts/notify-alert.sh` is the single transport and a no-op until
`PROMPTCODE_ALERT_WEBHOOK_URL` or `PROMPTCODE_ALERT_COMMAND` is set, so health
checking never depends on alerting being configured. Wired into
`check-prod-health.sh` (every failing gate reports its reason and measured
detail), `backup-db.sh` (an aborted backup), and the deploy workflow (a refused
deploy). Verified by `tests/test_alert_transport.py`, including a test proving a
failing health check reaches the destination rather than only exiting non-zero.
**Delivery to a real destination is unverified** — no endpoint is configured here.

**Health gates added.** Free disk below the reserve (from
`promptcode_interview_storage_free_bytes`) and per-worker stale heartbeats
(counted per row, so one dead replica among healthy ones is visible; the previous
global `MAX(last_seen_at)` hid it).

**Pre-migration backup.** `scripts/backup-db.sh --pre-migration` writes a local
database dump plus checksum and is invoked by the deploy workflow before the
backend container starts (migrations run on container start). It deliberately does
not require rclone so it cannot fail for an unrelated reason, and a failed dump
aborts the deploy. The full off-host backup is unchanged.

## 5c. Deployment, event loop and frontend overload

**Critical deployment bug fixed.** The production compose backend service never
mounted the artifact root, while both workers mounted it read-only. The backend's
configured `PROMPTCODE_INTERVIEW_WORKSPACE_ROOT` therefore resolved inside the
container's ephemeral filesystem: submitted source would be invisible to grading
workers and lost on restart. `docker-compose.prod.yml` now mounts the same host
path read-write for the API (the sole writer) and read-only for workers, with a
compose-contract test that fails if either side drifts.

**Event loop unblocked in two more places.** `_question_attachments` (workspace
walk plus file reads on every assistant message) and the `/internal/disk` walk now
run via `asyncio.to_thread`, so they no longer stall concurrent requests. The disk
endpoint reads its measurement through `workspace.storage_report`, which keeps the
transport layer out of storage internals — a violation my own boundary test caught
on the first attempt.

**Frontend overload handling.** `interview-api.js` now parses `Retry-After`,
marks 429/503 errors as retryable, and exposes `runTestsQueued`, which waits out
explicit capacity throttling under both an attempt cap and a 90 s deadline instead
of surfacing a raw error. The session page shows an explicit **QUEUED** state with
the retry delay (reusing the existing `busy` status tone) and, if the wait window
expires, tells the candidate their code is saved. Covered by
`tests/test_frontend_overload_contract.py`; the repository has no JS test runner,
so these are static contract checks, not executed browser behaviour.

**Read paths no longer take write locks.** `review_context` locked both the
session and evaluation rows with `FOR UPDATE`, and it backs the candidate report
and dashboard projection (`candidate_review_status`) as well as reviewer evidence.
Those are pure reads, so concurrent readers serialized against each other for no
benefit. The lock is now opt-in (`lock=True`) and taken only by the two paths that
actually mutate `evaluation.metrics` — `append_review` (which holds it through the
revision insert so two reviewers cannot compute the same revision) and the AI
feedback route.

**Grading probes run bounded-parallel.** A probe sweep executed its 3-7 inventory
cases sequentially inside one admitted execution slot: up to 84 s of slot
occupancy per job, the dominant contributor to grading-queue latency. The broker
now runs the independent read-only probes through a thread pool bounded by
`PROMPTCODE_PROBE_CONCURRENCY` (default 2), preserving inventory order and
per-case error attribution. Covered by `tests/test_probe_sweep_parallelism.py`.
The chosen concurrency is **not measured on a real execution host**: it is a
lower-risk starting point that requires live Docker verification before raising.

**Dashboard review projection is batched.** The dashboard called
`candidate_review_status` once per session row (up to 50), and each call issues
several queries — roughly 300 per dashboard load. The capacity workload ends each
simulated user flow with a dashboard read, so this sat directly on the measured
path. `published_reviews_for_sessions` answers the same question in a constant
number of queries and is covered by a parity test against the single-session
projection.

**Reconciliation ownership.** The API owns artifact writes and now also runs the
periodic ledger reconciliation from its lifespan. Grading workers mount the root
read-only, so the worker loop checks `ledger.is_writable()` and stands down instead
of warning every interval; on a genuinely read-only API mount it does the same and
per-write accounting still keeps totals correct. Covered by
`tests/test_storage_ledger_and_capacity.py`.

## 5d. Legacy code removed

`services/evaluation/ai_judge.py::ai_judge_evaluate` (226 lines) had no caller in
`app/`, `tests/`, `scripts/` or `benchmarks/` — a third, dead implementation of the
AI judge alongside the budgeted path. It was removed, along with the imports it
alone used.

Deliberately **kept**: `rubric.score_session` / `score_session_v2`. They are
legacy scorers, but the public `score_session_v2` is still reached from
`rubric.py` and both are exercised by contract tests
(`test_audit_execution_feedback.py`, `test_interview_mvp.py`,
`test_prep_session_architecture.py`). Removing them would also mean changing tests
that pin historical behaviour, which is out of scope for a behaviour-preserving
refactor. They are recorded here as legacy rather than silently deleted.

## 6. Remaining work (explicitly not done)

1. **Capacity rehearsal not re-run.** Needs Docker plus the prebuilt runner images.
   Run it and read the new `readiness_gates`/`capacity_validated` fields rather than
   the exit code alone.
2. **Grading progress in the frontend.** The session page now handles overload,
   but the report page still reads `assessment.execution_status` once and does not
   poll, so a queued grade appears as a static "Evaluation queued" label.
3. **Legacy AI gateway consolidation.** Both legacy judges now gate on budget
   before credentials, but they still call providers directly rather than through
   `ai_provider.py`, and the sandbox relay still reads the app provider key on the
   application host (the key does not enter the container, which is the intended
   design).
4. **Submit/report transaction scope.** `POST /submit` still holds a session row
   lock, a user row lock, the per-workspace lock and the global advisory lock
   across freeze and scoring; `GET /report` still takes write locks and re-hashes
   the submission. The statement timeout is now 30 s (configurable) so the
   10 s-vs-15 s conflict that produced 500s is gone, but the transaction scope
   remains the largest outstanding latency item.
5. **Probe sweep serialization.** A grading job holds one execution slot for the
   whole 3-7 case sweep at up to 12 s per case. Parallelizing it is the highest
   remaining grading-throughput lever and needs the live Docker tier to verify.
6. **Retention.** Workspaces referenced by any grading job are protected forever;
   there is no appeal-retention window and disk pressure is still a manual
   expansion.
7. **Still host-dependent**: the off-host backup destination and remote retention
   are unverified, and real alert delivery is unverified. (Existing-database
   upgrade/downgrade is now covered by the live migration tier above.)
8. **Legacy scorers retained** (`rubric.score_session` / `score_session_v2`) with
   contract tests still pinning them; see section 5d.
