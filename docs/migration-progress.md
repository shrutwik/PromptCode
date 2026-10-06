# Managed-deployment migration — shared progress log

One concise log for the Vercel + Supabase + Modal migration. Append one checkpoint
per completed stage. Do not rewrite history; correct with a new entry.

## Baseline (established before any change)

- Backend: FastAPI (`backend/app`), 823 Python modules under `backend/`, 102 test files.
- Test baseline: `745 passed, 70 skipped, 7 failed` — all 7 failures pre-exist this
  migration inside the in-flight uncommitted work (`test_config_security.py`,
  `test_audit_ai_controls.py`, `test_sandbox_proxy.py` disagree with the partially
  applied DeepSeek-pinning edit). Recorded, not introduced here. Stage 1 fixes the
  provider coupling that causes them.
- Execution today: public backend → HTTPS + bearer → `app/execution_broker.py`
  (separate service that owns the Docker socket) → `IsolatedRunner` /
  `_run_probe` run candidate code in Docker containers.
- Persistence today: workspace and immutable submission snapshots live on a shared
  host filesystem (`PROMPTCODE_INTERVIEW_WORKSPACE_ROOT`). Storage accounting uses an
  incremental SQLite ledger plus `fcntl` host locks. `interview_sessions.workspace_path`
  and `interview_grading_jobs.snapshot_path` store host paths.
- Jobs today: already durable and Postgres-backed
  (`evaluation_jobs`, `interview_grading_jobs`) with attempts, leases and recovery.

## Verified provider constraints (official docs, researched before design)

Source: see `docs/managed-deployment.md` for citations. Design-relevant facts:

- Modal: outbound network egress is **allowed by default**; `block_network=True` is
  required for a no-egress candidate sandbox.
- Modal: all web endpoints have a **150 s HTTP request timeout**, and the 303
  result-URL fallback does not work for CORS requests. Long grading therefore must use
  background spawn + poll, never a synchronous endpoint. The existing DB queue already
  provides this.
- Modal: a **payment method is required** to use the platform, including free credits.
  A workspace **spend limit** exists and must be set to `$0` to guarantee that credits
  are never exceeded into out-of-pocket charges.
- Supabase free: 500 MB database, 1 GB storage, 5 GB egress, **50 MB max single
  object**, project **paused after 7 days of database inactivity**, 60 direct
  connections, direct connections are IPv6-only, transaction-pool mode (6543) breaks
  prepared statements.
- Vercel Hobby: **non-commercial personal use only** (explicit policy). Hard-stops
  rather than billing when limits are exceeded.

## Stage contracts (frozen)

### Execution backend

`PROMPTCODE_EXECUTION_BACKEND` ∈ {`docker`, `modal`}; default `docker` keeps the
existing verified path byte-identical. Selected by
`app.services.execution.backend.get_execution_backend()`.

A backend exposes exactly the two primitives the codebase already needs:

```python
run_challenge(*, source_dir, argv, image, timeout_seconds, memory_mb, cpu_limit,
              output_limit_bytes, env) -> ChallengeRunOutcome
run_probe(*, source_dir, argv, image, timeout_seconds, output_limit_bytes) -> ProbeOutcome
```

Candidate sandboxes receive **no** application, database, provider or signing
credentials. Trusted comparison and grading-signature generation stay outside the
candidate environment (unchanged: `trusted_evaluator.evaluate_snapshot`).

### Persistence

`PROMPTCODE_STORAGE_BACKEND` ∈ {`filesystem`, `supabase`}; default `filesystem`
preserves local development. Selected by
`app.services.interview.object_store.get_object_store()`.

Object keys are provider-neutral and never host paths:

- workspace object: `workspaces/{session_id}/{rel_path}`
- immutable submission: `submitted/{session_id}/{source_digest}/{rel_path}`

The database is the source of truth. A local filesystem workspace is a **cache**
hydrated per container, never authoritative. Storage accounting moves from the SQLite
ledger to a Postgres table with atomic increments.

## Checkpoints

### Stage 0 — Recon (complete)
Read AGENTS.md, mapped execution/persistence/job/frontend paths, recorded the test
baseline, verified provider capabilities from official docs.

### Stage 1 — Contracts and configuration (complete)
- Added `execution_backend`, Modal settings, storage-backend and Supabase settings to
  `backend/app/core/config.py`, with validation.
- Replaced the hardcoded DeepSeek-only key assignment with provider-agnostic
  resolution (`resolve_ai_credentials`/`AICredentials`), so no vendor is required and
  a key is only ever sent to its own configured base URL. A mismatched
  `PROMPTCODE_AI_BASE_URL` is rejected at startup in every mode.
- Removed the hardcoded $5 trial cap default; the trial layer is opt-in
  (`PROMPTCODE_AI_TRIAL_ENABLED`) and every other cap (global/user/session,
  requests/tokens/cost) plus the kill switch remains enforced.
- Found and removed three further pieces of hardcoded vendor coupling that the
  in-flight work had introduced:
  - `_build_sandbox_llm_budget` overwrote challenge-declared `allowed_models` with a
    literal `("deepseek-flash",)` whenever the base URL was DeepSeek's. Now
    challenge constraints are never replaced, and a deployment may extend them with
    `PROMPTCODE_AI_MODEL_ALIASES`.
  - `legacy_broker_client` appended OpenAI model aliases only on the DeepSeek host.
    Now driven by the same configurable alias list.
  - `ai_provider._ai_api_key()` refused an explicitly configured AI-scoped key on a
    DeepSeek endpoint. An explicit `PROMPTCODE_AI_API_KEY` is now authoritative for
    every provider; legacy generic keys are still never forwarded to another vendor.

Verification:
- `pytest tests/test_config_security.py tests/test_audit_ai_controls.py
  tests/test_sandbox_proxy.py tests/test_prompt_quality_models.py` → **49 passed**.
- This clears all 7 pre-existing baseline failures. Four stale validator tests were
  made deterministic with `_env_file=None` (they were silently inheriting the
  developer's repo `.env`, which pins a provider and masked key validation); every
  assertion was kept. The budget test now explicitly enables the opt-in trial layer so
  it still covers all four persisted scope rows.
- Provider isolation proven: `openai` provider + a DeepSeek `ai_base_url` is rejected
  with a named error instead of forwarding the key; `custom` providers still work; the
  generic `PROMPTCODE_OPENAI_API_KEY` field still works as before.

Workstreams (in flight, strict file ownership — no shared-file parallel edits):
- Execution/security: `backend/app/services/execution/*` + `interview/runner.py`,
  `trusted_evaluator.py`.
- Persistence/jobs: `object_store.py`, `workspace_store.py`, `snapshot.py`,
  `workspace*.py`, `workers/interview_grading.py`, new alembic migration.
- Deployment/frontend: `backend/modal_app.py`, `vercel.json`, `startup_security.py`,
  `requirements.txt`, `.env.example`, `docs/managed-deployment.md`.

### Stage 2 — Deployment/frontend (complete, reviewed and corrected)

Delivered `backend/modal_app.py` (`@modal.asgi_app()` serving the unmodified FastAPI
app, a spawnable/scheduled background grading function, a Supabase keep-alive cron),
`vercel.json`, `docs/managed-deployment.md`, per-backend startup validation, the
`modal==1.6.1` dependency and a regenerated lock, and `.env.example`.

Independent review of that work found **three consequential defects**, all corrected
here and none of them self-reported:

1. **The Modal image was missing runtime data.** `app/services/interview/registry.py`
   resolves the challenge registry and every starter tree as `parents[4]/challenges`,
   and `app/services/evaluation/weight_profile.py` resolves `backend/benchmarks`. The
   image shipped only `backend/app`, so *no challenge could be started* — a hard
   blocker for the core workflow. Fixed by adding both directories to the image
   (`challenges/` with `node_modules` excluded: it is 608 MB of a 613 MB tree, is
   skipped by the starter copy, and belongs in the candidate sandbox image instead).
   `test_modal_app_ships_app_source_and_runtime_data` now asserts the required inputs.
2. **`vercel.json` rewrite destinations could not resolve.** Vercel serves the
   repository root (Root Directory stays at the repo root so the root `vercel.json` is
   read), but the pages live in `frontend/`; destinations of `/interview-challenges.html`
   point at a non-existent root path. Every destination now carries the `/frontend/`
   prefix while the public URLs stay clean. All 31 `/static/...` references were checked
   to resolve through `/static/:path* -> /frontend/:path*`.
3. **The Docker-daemon guard was dropped in modal mode.** The no-Docker-daemon
   invariant applies to every backend; it passes trivially in a correct Modal container
   and still rejects a Modal-configured app placed on a Docker host. Restored as a
   shared check, with the test inverted accordingly.

Also corrected in this review:
- `vercel.json`'s strict CSP was verified against the real frontend rather than trusting
  the report: 0 inline `<script>` blocks and 0 inline event handlers exist, so omitting
  `'unsafe-inline'` from `script-src` is safe; the only external origins used are
  `fonts.googleapis.com`, `fonts.gstatic.com`, `esm.sh` and `cdn.jsdelivr.net`, all
  permitted by the directives that use them.
- Three claims in `docs/managed-deployment.md` were contradicted by measurement and
  rewritten: the "every rewrite resolves" claim, the "socket/DOCKER_HOST are not
  failures in modal mode" claim, and the claim that re-running `pip-compile` produces no
  diff. The lock drift is **pre-existing** (a fresh compile of the *original*
  `requirements.txt` already differed from the *original* lock by 70 lines), so the CI
  lock gate fails independently of this migration; reconciling it means bumping ~70
  unrelated transitive pins and was deliberately left out of scope rather than hidden.

Verification: `pytest tests/test_deployment_contracts.py tests/test_audit_startup_security.py`
→ **206 passed** (83 + 123). `vercel.json` is valid JSON and every rewrite target
resolves to a real file.

### Stage 3 — Modal execution backend (complete)

`app/services/execution/` (`policy.py`, `modal_backend.py`, `backend.py`, `images.py`)
plus dispatch in `interview/runner.py` and `trusted_evaluator.py`. `PROMPTCODE_EXECUTION_BACKEND`
selects the backend; `docker` is the default and its code paths are unchanged, so local
development and the existing docker tests are unaffected.

Security properties enforced in code, not configuration:
- `block_network=True` on every `Sandbox.create`; `SandboxPolicy(block_network=False)`
  raises. This matters because Modal's default is that egress to any public IP is
  **allowed**.
- The sandbox environment is a fixed allowlist built key-by-key; nothing is copied from
  `os.environ`. A test sets nine secret-shaped variables (provider keys, JWT secret, DB
  URL, executor token, Supabase service-role key, `MODAL_TOKEN_*`, grading signing key)
  and proves none reach the sandbox environment.
- cpu/memory/timeout/pids/output clamped to hard bounds; the environment mapping is
  immutable.
- Termination on success, exception, timeout and cancellation, with the create-RPC race
  closed by reserving the run id before `create`.
- Output truncated tail-style to the policy bound, matching the Docker path's `_clip`.

Two defects were found and fixed inside this workstream:
1. The first implementation uploaded the candidate tree to `/workspace`, but
   `_probe_command` and `run.sh` read the tree at `/source` and build `/workspace`
   themselves — every probe would have failed. The backend now uploads to `/source`.
2. `run.sh` ends in `sleep 300` (a Docker tmpfs keep-alive), which would push every
   Modal advisory run into its deadline. Advisory runs use a service-owned `sh -c`
   bootstrap that mirrors the copy/dependency-link/exec sequence without the sleep.

**Modal hardening gaps, stated explicitly rather than overclaimed** (no Modal equivalent
in our code): `pids_limit` is only passed when the installed SDK's `Sandbox.create`
accepts it; there is no `read_only` root or `noexec/nosuid/nodev` tmpfs; and `cap_drop`,
`no-new-privileges` and a non-root UID have no counterpart — the sandbox image's `USER`
must set non-root. The Docker path additionally derived `ok` from the reporter
inventory for Python runs; the Modal advisory path is exit-code based and remains
advisory (`authoritative=False`).

Dependency layer: the sandbox images must contain
`/opt/promptcode-deps/<slug>/node_modules` built from `challenges/*/node_modules` (6
trees, ~608 MB) or Node probes fail per case. `images.py` documents the contract and
provides a build recipe; `docs/managed-deployment.md` §4.2.1 gives the operator both
routes (reuse the existing Dockerfiles and push to a registry, or build a Modal-native
image) and warns that a missing layer yields zero scores rather than an error.

Verification: `pytest tests/audit_runner_isolation.py tests/test_execution_broker.py
tests/test_sandbox_proxy.py tests/test_modal_execution_backend.py` → **71 passed**;
plus `test_trusted_evaluator.py`, `test_probe_sweep_parallelism.py`,
`test_architecture_boundaries.py` → **33 passed, 33 skipped** (live-Docker opt-in).

### Stage 4 — Managed persistence and grading dispatch (complete, narrowed)

Scope was deliberately narrowed after review: the storage-ledger replacement, capacity
accounting rework and advisory-lock conversion were dropped as scale work. Shipped is
only what the core workflow needs on ephemeral containers:

- `object_store.py` — the immutable submission in the private Supabase bucket under
  `submitted/{session_id}/{source_digest}/...`, via the authenticated Storage REST
  endpoint with the service-role key, bounded retry/backoff, idempotent puts, and the
  50 MB free-plan per-object cap enforced. The manifest object is uploaded **last** and
  is the commit marker, so an interrupted upload is never visible as complete.
- `workspace_store.py` — `ensure_workspace(db, session)` rebuilds a missing or empty
  container-local workspace from the starter tree plus the latest `interview_session_files`
  revision per path, wired into the nine file/AI/submit routes. Saved progress lives in
  the database; the local directory is only a cache.
- Migration `managed01_submission_object_key` adds the nullable `snapshot_key`.
- `workers/interview_grading.py` — `_execute` routes to the in-process trusted evaluator
  when `execution_backend == "modal"` (the blocker the deployment review raised: Modal has
  neither a broker URL nor a sandbox executor URL, so every claimed job would have failed).
  Submission identity is validated from the job row, and the source is hydrated and
  digest-verified.

Defect found and fixed during review of this workstream: staff review, appeal and retry
still read `job.snapshot_path` directly, which fails closed with a 409 in a fresh
container. A single shared `verified_job_source(job)` resolver now serves the worker and
all interactive readers. The interactive readers pass `require_ownership=False` because
they historically verified by digest only — an earlier revision of the resolver applied
the worker's stricter host-path check to them and broke that contract, which the existing
grading-review tests caught. One dropped `verify_snapshot` import was also caught by that
same test run.

Verification: `pytest tests/test_managed_storage.py tests/test_grading_review_workflow.py
tests/test_audit_grading_integrity.py tests/test_grading_snapshots_jobs.py
tests/test_grading_executor_boundary.py tests/test_grading_admission.py
tests/test_evaluate_cancellation.py tests/test_evidence_grading.py` → **105 passed**.

### Stage 5 — Full regression

`pytest tests/ -q` → **832 passed, 70 skipped, 0 failed** in 72.5 s.

For comparison, the baseline before this migration was **745 passed, 70 skipped, 7
failed**. The seven baseline failures were all pre-existing in-flight DeepSeek-pinning
work and are now resolved by the provider-agnostic configuration. Four further failures
that this migration introduced during development were found and fixed rather than
tolerated:
- `test_metrics.py` (2) and the AI-budget tests: the provider/base-URL mismatch was made a
  hard startup error, which was unnecessary strictness — `resolve_ai_credentials` already
  refuses to pair a key with another vendor's endpoint, so it is now a warning. `ai_budget`
  reads `ai_trial_enabled` defensively so partial settings objects still work.
- `test_shared_ai_budget.py::test_trial_budget_survives_daily_reset`,
  `test_audit_ai_controls.py::test_persistent_concurrent_global_user_session_budgets`:
  updated to enable the now opt-in trial layer explicitly, so they still cover the scope
  they were written against rather than being weakened.
- `test_beta_ai_hardening.py::test_session_budget_includes_assembled_test_output`: its
  session stub lacked `challenge_slug` and its DB a real `execute`, so workspace hydration
  could not run. Hydration is stubbed in that unit test (its subject is budget
  accounting); the hydration path has dedicated integration coverage.

### Stage 6 — Independent verification

An independent reviewer re-read the code adversarially and produced
`tests/test_managed_workflow_integration.py` (2 tests) and
`tests/test_managed_failure_modes.py` (7 tests). Both drive the real FastAPI routes with
the **documented managed profile** (`EXECUTION_BACKEND=modal`, `STORAGE_BACKEND=supabase`)
and the real `SupabaseObjectStore` code over a `MockTransport`, with only the `modal` SDK
stubbed. They prove: the full workflow (signup → login → start → read → save → run tests
in a Modal sandbox → edit survives workspace loss → submit → immutable bucket upload with
digest verification → durable worker re-hydrates from the bucket → completed report →
idempotent second drain), ownership rejection across users, and the failure modes
(duplicate submission, missing object, same-length tampering, a job repointed at another
session's key, cancellation of a starting sandbox, sandbox start failure, missing Modal
SDK). Each failure mode fails closed with no host fallback.

Two findings were consequential enough to fix:

1. **HIGH — "Run tests" never reached Modal in the documented configuration.**
   `get_challenge_runner()` returned `LocalDevelopmentRunner` unless
   `PROMPTCODE_RUNNER=docker`, but the managed profile deliberately leaves the runner at
   `local` (and forbids `ALLOW_UNSAFE_LOCAL_RUNNER`). Every test run would have answered
   `isolation:"host"`, `error_code:"unsafe_runner"`, with **zero sandboxes created** — the
   core workflow's "run real tests" step would have been dead on the deployed stack. This
   was live in the shipped configuration, not theoretical. Fixed by selecting
   `IsolatedRunner` when `execution_backend == "modal"` (its dispatcher routes the
   allowlisted argv to the Modal backend); the docker and local branches are unchanged.
   Reproduced failing before the fix, passing after.

2. **HIGH — the Vercel deployment would have published the answer keys.** No
   `.vercelignore` existed, and Vercel deploys the repository root. An existing static file
   wins over the SPA catch-all rewrite, so `challenges/<slug>/SOLUTION.md` (10 files, which
   `registry.py` deliberately blocks from the API) and `backend/**`, `docs/**`,
   `scripts/**` would all have been publicly served. Fixed with a root `.vercelignore`
   (`/*`, `!/frontend`, `!/vercel.json`); the gitignore semantics were verified with a real
   `git init` fixture showing only `frontend/**` and `vercel.json` survive, and
   `test_vercel_deployment_excludes_everything_but_the_frontend` now guards it.

Also corrected from review:
- The `assert ".spawn()" in source` deployment assertion was vacuous — the only `.spawn()`
  occurrences are in docstrings and no code spawns the grader. Replaced with an assertion
  that the ASGI function does not drain the queue (the real invariant), plus a note that
  grading latency is bounded by the poll.
- `ModalSandboxBackend.cancel()` documented a request-abort caller that does not exist.
  The docstring now states that termination is guaranteed by the timeout and `finally`,
  that no caller is wired yet, and that early cancellation is unverified.
- `get_object_store()` built a new `SupabaseObjectStore` (and `httpx.Client`) on every
  call, leaking a connection pool per submission and per grading attempt. It is now cached
  per process, keyed on the store class, URL and bucket so a replaced store (as tests do)
  still gets a fresh instance.

Confirmed not defective: no existing test was weakened, deleted or made vacuous; the suite
does not hang (an earlier apparent hang was piped-output contention); and the reviewer
corrected its own false positive about `test_metrics.py` after a direct run finished in
0.87 s.

Remaining gaps are recorded in `docs/managed-deployment.md` §5.1 (G1–G7): no bucket
retention/cleanup on the managed stack, no automated build path for the two sandbox images,
one documented-but-unread keep-alive setting, unwired cancellation, container-vs-bucket
storage accounting, and Postgres-specific paths exercised only against SQLite.

Final state: `pytest tests/ -q` → **833 passed, 70 skipped, 0 failed**.





