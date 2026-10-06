# PromptCode target architecture and staged migration plan

Status: **stages 1-4 implemented and locally verified; stages 5-6 partly done.**
Local evidence, measurements and the explicit not-done list are in
[refactor-verification.md](refactor-verification.md). The read-only audit reports
live in `.audit/agent-*.md`. Nothing in this document claims production capacity.

## 1. What the application is today

Single-host Docker Compose stack:

| Process | Role | Deployment artifact |
| --- | --- | --- |
| `caddy` | TLS termination, reverse proxy | `docker/Caddyfile.prod` |
| `backend` | FastAPI API + static frontend + runs migrations at start | `app/main.py`, `scripts/run_with_migrations.py` |
| `worker`, `worker-b` | Durable evaluation and interview-grading job loops | `app/workers/queue.py`, `app/workers/interview_grading.py` |
| `sandbox-executor` | Credential-free host that owns the Docker daemon and runs candidate code | `app/execution_broker.py`, `app/sandbox_executor.py` |
| `db` | PostgreSQL, the only persistent data store | `alembic/` |

Candidate artifacts live on a shared filesystem (`PROMPTCODE_INTERVIEW_WORKSPACE_ROOT`) that the
backend and every worker must share. Immutable submissions are written under `.submitted/`.

## 2. Ownership and dependency rules (target)

Modules stay inside **one application**; candidate execution is the only separate process boundary,
and it already exists. No new services are proposed: none of the measured bottlenecks requires one.

Layering rule, enforced by convention and import direction (top may import down, never the reverse):

```
transport (app/api/routes/*)      HTTP parsing, auth dependency, status mapping. No DB queries
                                  beyond calling a service, no filesystem work, no provider calls.
workflows (app/services/interview/*, app/services/evaluation/*)
                                  Business rules: sessions, workspaces, snapshots, grading,
                                  review/appeal, budgets. The only place business rules live.
gateways (app/services/interview/ai_provider.py, app/services/sandbox/*)
                                  Outbound calls: provider, execution broker/relay. Credentialed.
jobs (app/workers/*)              Durable claim/lease/retry/recovery loops. Calls workflows.
data (app/db/*, app/models/*)     Session factory, model definitions, migration helpers.
runtime (app/core/*)              Config, security, logging, metrics, limits, transport knobs.
```

| Domain | Owner module | May import | Must not |
| --- | --- | --- | --- |
| API + authentication | `app/api/routes/auth.py`, `app/core/security.py`, `app/core/deps.py` | workflows, data, runtime | provider calls, Docker |
| Interview workflows | `app/api/routes/interview.py`, `app/services/interview/{lifecycle,workspace,snapshot,registry,rubric,levels}.py` | data, runtime, gateways | Docker directly (goes through `services/interview/runner.py`) |
| AI gateway + persistent budgets | `app/services/interview/ai_provider.py`, `ai_budget.py`, `app/models/ai_budget.py` | runtime, data | transport |
| Durable job scheduling | `app/workers/*`, `app/services/interview/grading_admission.py` | workflows, data | transport |
| Isolated execution | `app/execution_broker.py`, `app/sandbox_executor.py`, `app/services/sandbox/*`, `app/services/runner_capacity.py` | runtime only | app DB, JWT/signing/provider secrets |
| Grading + human review | `app/services/interview/{grading,trusted_evaluator,grading_review,grading_feedback,grading_calibration}.py`, `trusted_cases/`, `reporters/` | data, runtime, ai gateway | transport |
| Database, workspaces, immutable submissions | `app/db/*`, `app/services/interview/{workspace,workspace_quota,snapshot,cleanup}.py` | runtime | transport, providers |
| Operations + monitoring | `app/core/metrics.py`, `app/core/logging.py`, `scripts/*` | everything (read-only) | mutating business state |

Dependency direction is checked by `backend/tests/test_architecture_boundaries.py` (added by this
work) so the rule cannot silently rot.

## 3. Canonical implementations

| Concern | Canonical | Legacy / duplicate | Migration stance |
| --- | --- | --- | --- |
| Interview grading | `services/interview/grading.py` + `trusted_evaluator.py` + durable `InterviewGradingJob` | `services/evaluation/*` + `app/workers/evaluate.py` (challenge/evaluation pipeline) | Keep both only while `challenges/` submissions remain served. Every legacy paid path must share budgets. |
| Candidate execution | `services/interview/runner.py` → broker `/v1/interview/run` (credential-free) | `services/sandbox/runner.py`, `sandbox/executor` URL path, `services/sandbox/legacy_broker_client.py` | Migrate callers, then retire the in-process Docker path. |
| AI provider access | `services/interview/ai_provider.py` + `ai_budget.reserve_*` | `services/evaluation/ai_judge.py`, `services/evaluation/prompt_quality.py` (direct `httpx`/`openai`) | Route all paid calls through the shared gateway and budget; the legacy judge must never call a provider after a budget denial. |
| Storage accounting | one incremental accounting module (this work) | `workspace_quota.retained_bytes`/`usage` full scans under one global lock | Replace per-write scans with atomic counters; keep the scanner for reconciliation and metrics. |
| Queue claiming | `workers/queue.py` (`FOR UPDATE SKIP LOCKED` + conditional `UPDATE ... RETURNING`) and `workers/interview_grading.py` (lease token) | — | Already canonical; fix per-poll unconditional sweeps. |

Docstring and module responsibility for each canonical module is recorded in the module itself.

## 4. Measured bottlenecks and their fixes

Measurements are from `docs/capacity-local-results.json` (2026-10-05, single shared developer host,
4 execution slots, 2 workers, paid AI disabled):

| Stage | Workflows | Session-create p95 | Source-save p95 | Grading queue p95 | Advisory shed |
| --- | --- | --- | --- | --- | --- |
| 50 | 50/50 | 10.51 s | — | 20.56 s | 80.3% |
| 100 | 100/100 | 28.78 s | 7.43 s | 52.67 s | 84.1% |

1. **Storage accounting is quadratic.** Every source save runs `check_upload()` → full `os.walk` of
   the session workspace (`workspace_quota.py:75-80`) and then `storage_capacity()` → full `os.walk`
   of the *entire* artifact root while holding a host-wide exclusive lock
   (`workspace_quota.py:17-49`). With N sessions the per-save cost grows with total retained bytes,
   and all saves serialize. Fix: atomic incremental counters with reservation/release semantics;
   the full walk remains for reconciliation and metrics only.
2. **Execution capacity rejects instead of queueing.** `services/runner_capacity.py:18-30` raises
   `RunnerBusy` when all slots are taken; `services/interview/runner.py:493-499` returns
   `runner_busy` when more than `2 × max_runners` callers wait or a 15 s acquire times out;
   `execution_broker.py:140-141` returns HTTP 503. The client sees an overload error, so a workload
   that intentionally overloads produces 80-84% shed responses. Fix: bounded, fair waiting queue with
   an explicit `queued` state and a bounded deadline, plus a hard cap on queued waiters.
3. **The capacity harness cannot fail on shedding.** `capacity_validated` is hardcoded `false` and the
   documented 25% advisory-shedding readiness gate is recorded but never enforced; the process exits
   non-zero only on incomplete workflows. Fix: make the readiness gates part of the exit condition,
   with the threshold configurable by flag.
4. **Grading workers issue unconditional sweeps every poll.** `workers/interview_grading.py:37-44`
   runs two `UPDATE` statements each poll regardless of whether any row matches. Fix: predicate the
   updates so an idle queue performs no write.
5. **Full-scan metrics.** `core/metrics.py:70` walks the artifact tree on every `/metrics` scrape.
   Fix: read the accounting counters; keep the walk on a slower reconciliation path.

## 5. Non-negotiables this plan preserves

- Authorization and API contracts are unchanged unless a migration is documented here. The frontend
  (`frontend/*.html`, `frontend/js/*`, `frontend/api.js`, `frontend/interview-api.js`) keeps working.
- Saved work, `.submitted` immutable snapshots, grading evidence, review revisions and appeals are
  never overwritten or deleted by a refactor. Cleanup retains anything referenced by a grading job,
  review or appeal (`services/interview/cleanup.py`).
- Candidate execution never receives application, database, signing or provider credentials
  (`core/config.py:189-198` enforces this at startup; `execution_broker.py` is credential-free).
- Every paid AI path uses the shared persistent budget and the kill switch. Spending controls do not
  depend on topic filtering.
- The configured $5 total AI trial budget is unchanged. **No paid provider call is made during
  verification.**
- Concurrency, queue, retry, runtime, memory, disk, request-size and retained-storage bounds stay in
  place or tighten; none are raised to make a test pass.

## 6. Staged migration plan

Each stage is independently verifiable and leaves the application working.

| Stage | Scope | Verification |
| --- | --- | --- |
| 1 | Baseline: hermetic test runner, recorded baseline results, architecture boundaries test, this document | Full suite; boundary test |
| 2 | Canonicalization: make the legacy AI judge honour the budget before credentials; route remaining paid paths through the gateway; document canonical modules | Targeted budget/provider tests |
| 3 | Bottlenecks: incremental storage accounting; bounded fair execution queue; grading sweep predicates; counter-based metrics | Storage/quota/broker/worker tests + repeat the 50/100 capacity rehearsal |
| 4 | Integration and recovery: full workflow, leases, duplicate jobs, storage exhaustion, interrupted execution | Full suite + live tier where Docker is available |
| 5 | Remove obsolete paths only after replacement behavior is verified | Full suite |
| 6 | Documentation: setup, deployment, operations, backup/restore, rollback limits | Doc review against scripts |

## 7. Rollback and migration limitations

- Alembic revisions are additive for this work; no destructive schema change is planned. The existing
  `9fb7f8d6f3b1` leaderboard dedupe deletes rows and is **not** reversible; any downgrade past it
  loses data.
- `scripts/run_with_migrations.py` upgrades on backend start with a bounded retry but **no advisory
  lock**; two backends starting together can both attempt DDL. Documented limitation; a pre-migration
  backup is not taken by the deploy job today.
- Application image rollback does not roll back schema. Downgrade one revision explicitly and verify
  before relying on an older image (`docs/first-deploy-runbook.md`).
- Storage counters introduced in stage 3 are derived state: if they are ever wrong, the reconciliation
  walk in the accounting module is authoritative and rebuilds them. No candidate data depends on them.

## 8. Explicitly unverified

- Production capacity, latency acceptance and resource headroom: **not claimed**. The only evidence is
  a local rehearsal on a shared developer host.
- Real provider behaviour, billing and token accounting: **not tested** (no paid calls permitted).
- Real Docker isolation, real-Postgres lease/admission concurrency and ENOSPC: opt-in tests only
  (`PROMPTCODE_AUDIT_DOCKER=1`), not part of the default suite.
- Off-host backup destination, alert delivery and existing-database upgrade: require a configured host.
