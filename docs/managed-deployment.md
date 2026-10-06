# Managed deployment: Vercel + Modal + Supabase

This runbook covers the managed stack that replaces the self-managed
`docker-compose` host for a free-tier beta:

| Layer | Provider | Runs |
|-------|----------|------|
| Static frontend | **Vercel** (`frontend/`, plain HTML/JS/CSS, no build step) | `frontend/index.html`, `frontend/interview-*.html`, `frontend/api.js`, `frontend/interview-api.js` |
| Backend API + background grading | **Modal** (`backend/modal_app.py`) | `app.main:app` (FastAPI), the durable grading worker, a keep-alive cron |
| Postgres + private object storage | **Supabase** | database, private storage bucket |

Deployment artifacts owned by this runbook:

- `backend/modal_app.py` — Modal App, image, ASGI endpoint, background grading function, keep-alive.
- `vercel.json` — static hosting, `/api/*` proxy to Modal, security headers, route rewrites.
- `backend/app/core/startup_security.py` — startup validation per execution backend.
- `backend/requirements.txt` — `modal` pin (the Modal image installs this file).
- `.env.example` — every new setting, grouped (the "Managed deployment profile" section at the end).

> The self-managed Docker deployment remains fully supported and its checks are
> unchanged. Everything below is additive.

---

## 1. Account setup

### 1.1 Modal (backend)

1. Create a Modal account, then **add a payment method** on the
   [Usage & Billing](https://modal.com/settings/usage) page. Modal requires a payment
   method on file ([Billing](https://modal.com/docs/guide/billing)).
2. **Required step — set the workspace spend limit to `$0`.** Usage & Billing →
   **Spend limit** → `0`. The spend limit caps *net charges after credits are
   applied*, so `$0` guarantees that when free credits are exhausted Modal stops
   workloads instead of charging your card. Without a custom spend limit, Modal
   defaults it to `usage limit − credits`, which can be greater than `$0`
   ([Budgets → Spend limits](https://modal.com/docs/guide/budgets)).
   Only Owners and Managers can set it.
3. Authenticate the CLI on the machine that deploys:
   ```bash
   python -m pip install modal==1.6.1
   modal token new          # or: modal setup
   modal profile current    # confirm the target workspace/environment
   ```
4. Create the runtime secret once (see §2.2). `modal deploy` fails if the secret
   named by `PROMPTCODE_MODAL_SECRET_NAME` (default `promptcode-env`) does not exist.
5. Optional: an Environment per stage (`modal deploy -e staging ...`). The web URL
   then carries the environment's web suffix
   ([Environments](https://modal.com/docs/guide/environments)).

### 1.2 Supabase (database + object storage)

1. Create a project on the free plan.
2. Project Settings → Database → **Connection string** → *URI*. Use the **Session
   pooler** (`...pooler.supabase.com:5432`) and replace `postgresql://` with
   `postgresql+asyncpg://`. The session pooler avoids two free-plan sharp edges:
   direct connections are **IPv6-only**, and the free plan allows **60 direct
   connections**
   ([Connecting to Postgres](https://supabase.com/docs/guides/database/connecting-to-postgres)).
3. The **transaction pooler** (`:6543`) also works because the application already
   disables asyncpg's prepared-statement cache for Postgres
   (`backend/app/db/session.py` and `backend/alembic/env.py` both set
   `statement_cache_size=0`). PgBouncer's transaction mode does not support
   server-side prepared statements, which is the failure it prevents
   ([Disabling prepared statements](https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL)).
   If you switch pool modes, keep that setting; the session pooler remains the
   lower-risk default.
4. Storage → create a **private** bucket (default name `promptcode-private`, matching
   `PROMPTCODE_SUPABASE_STORAGE_BUCKET`). Never make it public.
5. Copy the **service-role** key from Project Settings → API. It is a backend-only
   secret (§2.3) — it bypasses row-level security, so it must never reach the
   frontend or a candidate sandbox.
6. Free projects **pause after 7 days without database activity**
   ([Project pausing](https://supabase.com/docs/guides/platform/free-project-pausing)).
   `modal_app.py` schedules a `SELECT 1` (`supabase_keepalive`) every 6 hours to
   prevent that; it is gated on `PROMPTCODE_SUPABASE_KEEPALIVE_ENABLED`.
7. Free plan has **no automated backups**
   ([Backups](https://supabase.com/docs/guides/platform/backups)) — see §3.

### 1.3 Vercel (static frontend)

1. Import the repository. **Leave Root Directory at the repository root**: the
   `vercel.json` that defines the `/api/*` proxy and the security headers lives at the
   root, and `frontend/` has no `package.json` or build step. Do not set a framework
   preset or build command. Because the deployment root is the repository root, every
   rewrite/redirect destination in `vercel.json` is prefixed with `/frontend/` (the
   public URLs stay clean, e.g. `/challenges` and `/session/:id`).
2. Confirm the project has no `outputDirectory`/`buildCommand` overrides in the
   dashboard: the deployment is plain static files.
3. Note the plan policy: **Vercel Hobby is for non-commercial personal use only**
   ([Hobby plan](https://vercel.com/docs/plans/hobby), [Fair use](https://vercel.com/docs/limits/fair-use-guidelines)).
   A commercial deployment needs a paid plan. Hobby also hard-stops when limits are
   exceeded instead of billing for overage ([Limits](https://vercel.com/docs/limits)).
4. Static `rewrites` in `vercel.json` are supported on Hobby
   ([Project configuration](https://vercel.com/docs/project-configuration),
   [Rewrites](https://vercel.com/docs/rewrites)).

---

## 2. Secrets: what lives where

### 2.1 Where each secret belongs

| Secret | Lives | Never |
|--------|-------|-------|
| `PROMPTCODE_DATABASE_URL`, `PROMPTCODE_SUPABASE_SERVICE_ROLE_KEY`, `PROMPTCODE_JWT_SECRET`, `PROMPTCODE_GRADING_SIGNING_KEY`, `PROMPTCODE_INTERVIEW_INTERNAL_TOKEN`, `PROMPTCODE_METRICS_TOKEN`, provider keys (`DEEPSEEK_API_KEY`, `PROMPTCODE_OPENAI_API_KEY`, `PROMPTCODE_AI_API_KEY`) | Modal Secret `promptcode-env` (trusted backend container) | frontend files, `vercel.json`, browser storage, candidate sandboxes |
| `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | Modal Secret `promptcode-env` (the SDK reads them to create Sandboxes) | any candidate sandbox, the frontend, this repository |
| `PROMPTCODE_SUPABASE_URL`, `PROMPTCODE_SUPABASE_STORAGE_BUCKET`, `PROMPTCODE_MODAL_APP_NAME`, `PROMPTCODE_MODAL_SANDBOX_IMAGE_*` | Non-secret configuration; safe in the Modal Secret or as plain env vars | — |
| Vercel project settings | Only the deployment configuration in `vercel.json` — **no application secrets** | — |

The frontend is unauthenticated static content: it holds no provider, database or
signing secret. `frontend/api.js` and `frontend/interview-api.js` call
`window.location.origin + "/api/..."`, which Vercel proxies to Modal, so the browser
never needs a backend credential.

### 2.2 Create the Modal secret

```bash
modal secret create promptcode-env \
  PROMPTCODE_DATABASE_URL='postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres' \
  PROMPTCODE_DATABASE_SSL_REQUIRE=true \
  PROMPTCODE_JWT_SECRET='<32+ random bytes>' \
  PROMPTCODE_GRADING_SIGNING_KEY='<32+ random bytes>' \
  PROMPTCODE_INTERVIEW_INTERNAL_TOKEN='<random>' \
  PROMPTCODE_METRICS_TOKEN='<random>' \
  DEEPSEEK_API_KEY='<provider key>' \
  PROMPTCODE_AI_PROVIDER=deepseek \
  PROMPTCODE_EXECUTION_BACKEND=modal \
  PROMPTCODE_STORAGE_BACKEND=supabase \
  PROMPTCODE_SUPABASE_URL='https://<project-ref>.supabase.co' \
  PROMPTCODE_SUPABASE_SERVICE_ROLE_KEY='<service-role key>' \
  PROMPTCODE_SUPABASE_STORAGE_BUCKET=promptcode-private \
  PROMPTCODE_MODAL_SANDBOX_IMAGE_NODE='<node sandbox image>' \
  PROMPTCODE_MODAL_SANDBOX_IMAGE_PYTHON='<python sandbox image>' \
  DOMAIN='<your Vercel hostname, e.g. promptcode.vercel.app>' \
  MODAL_TOKEN_ID='<modal token id>' \
  MODAL_TOKEN_SECRET='<modal token secret>'
```

`modal secret create` with an existing name creates a new version; run
`modal secret list` to confirm. Every `PROMPTCODE_*` setting an operator changes must
live in this secret (or in the environment of whatever process runs the app) — never
in the image, the repository, or the frontend.

> `PROMPTCODE_MODAL_*` deploy-time knobs read by `modal_app.py` on the *deploying*
> machine (`PROMPTCODE_MODAL_SECRET_NAME`, `PROMPTCODE_MODAL_KEEPALIVE_CRON`,
> `PROMPTCODE_MODAL_GRADING_POLL_SECONDS`, `PROMPTCODE_MODAL_GRADING_MAX_CONTAINERS`)
> are deliberately not `Settings` fields and must not be put in `.env.example`
> (`scripts/validate-env.sh` rejects variables that are not referenced by
> `config.py` or compose).

---

## 3. Database migrations and rollback

Migrations run against Supabase from a machine with the repository checked out — the
same Alembic revision chain the Docker deployment uses.

```bash
cd backend
export PROMPTCODE_DATABASE_URL='postgresql+asyncpg://postgres.<ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres'
export PROMPTCODE_DATABASE_SSL_REQUIRE=true
export PROMPTCODE_JWT_SECRET='<any non-empty value; alembic/env.py loads Settings>'
python -m alembic upgrade head          # apply
python -m alembic current               # confirm the head revision
```

Take a logical backup **before** any migration: the Supabase free plan has no
automated backups, and `scripts/backup-db.sh` is docker-compose specific. Use
`pg_dump` directly:

```bash
pg_dump --format=custom --no-owner --no-privileges \
  "$PROMPTCODE_DATABASE_URL" > promptcode-$(date +%Y%m%dT%H%M%S).dump
```

Rollback procedure (reverse order of deployment):

1. **Application first.** Modal → Apps → your app → previous deployment → *Rollback*
   (or re-run `modal deploy backend/modal_app.py` from the previous commit). Vercel →
   Deployments → previous deployment → *Promote to Production*. Rolling the
   application back first is what the repository's ops rehearsal
   (`.github/workflows/ops-rehearsals.yml`, `rollback_boundary_probe`) is designed to
   prove: the previous image tolerates the newer schema.
2. **Then the schema**, only if the release added a migration that must be undone:
   ```bash
   cd backend && python -m alembic downgrade -1
   ```
   Downgrades that drop columns lose data. Prefer rolling forward with a fix; restore
   from the `pg_dump` above if a downgrade is unavoidable.
3. Restore the database if needed:
   ```bash
   pg_restore --clean --if-exists --no-owner --dbname "$PROMPTCODE_DATABASE_URL" <backup>.dump
   ```

---

## 4. Deployment steps

Deploy in this order: **Supabase → Modal → Vercel**. Vercel needs the Modal URL, and
Modal needs the Supabase credentials.

### 4.1 Supabase

1. Create the project and the private bucket (§1.2).
2. Run the migrations (§3) and confirm `python -m alembic current` matches head.
3. Seed challenge data if this is a fresh database (`scripts/seed-prod-data.sh` is
   docker-compose specific; from `backend/` run the equivalent seeding routine the
   repository uses for the environment).

### 4.2 Modal

```bash
# from the repository root
modal deploy backend/modal_app.py
```

This deploys one App (`PROMPTCODE_MODAL_APP_NAME`, default `promptcode`) with:

| Function | Trigger | Purpose |
|----------|---------|---------|
| `fastapi_app` | `@modal.asgi_app()` | serves the unmodified `app.main:app` over HTTPS |
| `grade_pending_jobs` | `modal.Period` (default 60 s) **and** `.spawn()` | drains the durable Postgres grading queue via `process_one_grading_job` |
| `supabase_keepalive` | `modal.Cron` (default `0 */6 * * *`) | `SELECT 1` so the free Supabase project is not paused |

Notes:

- The image installs `backend/requirements.txt` and ships `backend/app`.
- The frontend is intentionally absent (Vercel serves it).
- **The image must also ship `challenges/` and `backend/benchmarks/`**, and it does:
  `app/services/interview/registry.py` resolves the challenge registry and every
  starter tree as `parents[4]/challenges`, and
  `app/services/evaluation/weight_profile.py` resolves the evaluator weight profile
  as `parents[3]/benchmarks`. Without them the app boots but *no challenge can be
  started*. `challenges/` is added with `node_modules` excluded (it is 608 MB of a
  613 MB tree, is skipped by the starter copy, and belongs in the sandbox image).
- Grading is a plain Function, not a web endpoint, so the **150 s Web Function HTTP
  timeout** does not apply
  ([Request timeouts](https://modal.com/docs/guide/webhook-timeouts)). It runs the
  existing lease-based claim loop, so several runs (a scheduled tick plus an eager
  spawn) are safe and cannot publish the same result twice. The database remains the
  single source of truth.
- Optional low-latency trigger from the API after enqueueing a grading job:
  ```python
  from modal import Function
  Function.from_name("promptcode", "grade_pending_jobs").spawn()
  ```
  Without it, a submission waits up to one poll interval (`PROMPTCODE_MODAL_GRADING_POLL_SECONDS`).
- Canary the app without a public URL: `modal serve backend/modal_app.py`.

### 4.2.1 Build the two candidate sandbox images (required before grading works)

`PROMPTCODE_MODAL_SANDBOX_IMAGE_NODE` and `PROMPTCODE_MODAL_SANDBOX_IMAGE_PYTHON`
are consumed by `app/services/execution/modal_backend.py` through
`modal.Image.from_registry(...)`, so both must be **pullable registry references**
(local Docker tags such as `promptcode-runner-node:latest` cannot be pulled by
Modal). They must reproduce the Docker runner layout, because the service-owned
command builders address these exact paths
(`app/services/execution/images.py` documents the same contract):

| Path | Provided by |
|------|-------------|
| `/source` | written per run by the backend (the validated candidate tree) |
| `/workspace` | built per run by the probe/bootstrap code |
| `/opt/promptcode-deps/<slug>/node_modules` | the image (reviewed per-challenge Node deps; the probe loads esbuild from here) |
| Node 20 / Python 3.12 + pytest toolchain | the image |

Two ways to produce them; either is fine, the settings must point at the result:

1. **Reuse the existing Dockerfiles and push to a registry** (no new build logic).
   `docker/Dockerfile.interview-node` already builds `/opt/promptcode-deps/` from
   `challenges/*/node_modules`, and `docker/Dockerfile.interview-python` covers the
   Python stack:
   ```bash
   docker build -f docker/Dockerfile.interview-node   -t <registry>/promptcode-runner-node:<tag>   .
   docker build -f docker/Dockerfile.interview-python -t <registry>/promptcode-runner-python:<tag> .
   docker push <registry>/promptcode-runner-node:<tag>
   docker push <registry>/promptcode-runner-python:<tag>
   ```
   The images must be readable by Modal: use a public repository, or add registry
   credentials to the Modal Secret (the current backend calls `from_registry(ref)`
   with no credential argument).
2. **Build a Modal-native image** with the helper in
   `app/services/execution/images.py` (`build_sandbox_image` +
   `challenge_dependency_mounts`), publish it, and set the settings to the published
   reference.

If these images are missing the dependency layer, the Node trusted probes fail per
case with `candidate_error`, i.e. grading returns zeros rather than an error — so
verify with a real submission after the first deploy, not only with `/health`.


### 4.3 Vercel

1. Import the repository (root directory = repository root), deploy.
2. Get the API URL from the `modal deploy` output or the Modal dashboard
   (Apps → `promptcode` → `fastapi_app`). By default the label is
   `<app>-<function>`, i.e. `https://<workspace>[--<environment-suffix>]--promptcode-fastapi-app.modal.run`
   ([Web Function URLs](https://modal.com/docs/guide/webhook-urls)). Confirm it:
   ```bash
   curl -fsS https://<workspace>--promptcode-fastapi-app.modal.run/health
   # {"status":"ok"}
   ```
3. Replace the placeholder in `vercel.json` and redeploy:
   ```json
   { "source": "/api/:path*",
     "destination": "https://<workspace>--promptcode-fastapi-app.modal.run/api/:path*" }
   ```
   `vercel.json` is a static file: Vercel does not interpolate environment variables
   into `rewrites.destination`, so the Modal origin must be written literally (or the
   frontend base URL must be made configurable at deploy time, which this migration
   deliberately avoids to keep `frontend/` free of build tooling and hardcoded
   environment handling). Replacing the placeholder is a one-line commit.
4. Set `DOMAIN` (and `PROMPTCODE_CORS_ORIGINS` if anything calls the Modal URL from a
   different origin) to the Vercel hostname. Because `/api/*` is proxied, browser
   requests are same-origin and CORS is not exercised in normal use.

### 4.4 Post-deploy verification

```bash
curl -fsS https://<vercel-host>/api/health              # proxied to Modal
curl -fsS https://<workspace>--promptcode-fastapi-app.modal.run/health/ready
curl -fsSI https://<vercel-host>/ | grep -i content-security-policy
curl -fsSI https://<vercel-host>/static/css/pc-tokens.css   # /static/* rewrite
curl -fsS https://<vercel-host>/dashboard | grep -i interview-dashboard
```

Also check, in order of importance: the grading queue drains (Modal → App → logs for
`grade_pending_jobs`), `alembic current` equals head, and the Modal usage page still
shows a `$0` spend limit.

---

## 5. Free-tier limits and blockers

| # | Limit or blocker | Consequence for this stack | Source |
|---|------------------|----------------------------|--------|
| 1 | Modal web endpoints have a **150 s** HTTP request timeout; the 303 result-URL fallback **does not work for CORS requests** | No request may synchronously wait for grading. Grading stays a durable DB job + polling; the grading worker is a background Function. Any future endpoint that would exceed 150 s must spawn a job instead | [Request timeouts](https://modal.com/docs/guide/webhook-timeouts) |
| 2 | Modal **requires a payment method**, and the default spend limit equals `usage limit − credits` | **Set the workspace spend limit to `$0`** so credits are never exceeded into out-of-pocket charges. This is a required manual step in §1.1 and cannot be set from code | [Budgets](https://modal.com/docs/guide/budgets), [Billing](https://modal.com/docs/guide/billing) |
| 3 | Modal **sandbox egress is allowed by default**; `block_network=True` is opt-in | Candidate code could reach the network unless the sandbox code sets `block_network=True`. Owned by the sandbox implementation (`backend/app/services/execution/*`), not by this change — verify it before exposing grading to untrusted input | [Sandbox networking](https://modal.com/docs/guide/sandbox-networking) |
| 4 | Supabase free plan: **500 MB database, 1 GB storage, 5 GB egress, 50 MB maximum single object**, project **paused after 7 days of DB inactivity**, **60 direct connections**, direct connections are **IPv6-only**, **no automated backups** | The 50 MB per-object cap is far below the application's default `PROMPTCODE_INTERVIEW_STORAGE_MAX_BYTES` (20 GiB): keep `PROMPTCODE_SUPABASE_MAX_OBJECT_BYTES` ≤ 50 MB (Settings rejects more) and size retention to ≤ 1 GB. The default `PROMPTCODE_DATABASE_POOL_*` (20 + 10 per process) must fit the pooler's limits, not the 60 direct connections. Pausing is mitigated by `supabase_keepalive`; **backups are the operator's job** (§3, §4.1) | [Pricing](https://supabase.com/pricing), [Project pausing](https://supabase.com/docs/guides/platform/free-project-pausing), [Backups](https://supabase.com/docs/guides/platform/backups) |
| 5 | Supabase **transaction pooler (6543) breaks prepared statements** | The app already sets `statement_cache_size=0` (`app/db/session.py`, `alembic/env.py`), so both poolers work; the session pooler (5432) is still the recommended default and is required if any future component uses prepared statements | [Disabling prepared statements](https://supabase.com/docs/guides/troubleshooting/disabling-prepared-statements-qL8lEL) |
| 6 | Vercel **Hobby is non-commercial personal use only**; Hobby **hard-stops** at limits (no overage billing) | Do **not** describe a Hobby deployment as commercially production ready. Static `rewrites` are supported on Hobby, so the proxy works; a commercial launch needs a paid Vercel plan | [Hobby plan](https://vercel.com/docs/plans/hobby), [Fair use](https://vercel.com/docs/limits/fair-use-guidelines), [Limits](https://vercel.com/docs/limits) |
| 7 | Modal billing is per-second of container runtime, including cold starts | The 60 s grading poll starts a container per tick whether or not a job is queued. Raise `PROMPTCODE_MODAL_GRADING_POLL_SECONDS`, or spawn `grade_pending_jobs` from the API and widen the poll, if credits matter more than grading latency | [Budgets](https://modal.com/docs/guide/budgets) |

---

## 5.1 Known remaining gaps (found by independent review, not fixed here)

These are real and were deliberately left for the next pass rather than half-implemented.
None blocks the core workflow on day one; each has a stated trigger.

| # | Gap | What breaks, and when |
|---|-----|-----------------------|
| G1 | **No retention or cleanup is scheduled on the managed stack.** `SupabaseObjectStore.delete_prefix` has no caller, `cleanup_interview_resources` only runs from `backend/scripts/cleanup_interview_sessions.py` (self-managed host), and `workspace_quota.storage_capacity` measures `workspace_root()`, which on Modal is a per-container ephemeral directory rather than the bucket. | The private bucket only grows. Once the 1 GB free allowance is full, `persist_submission` raises and **submit returns 409 "Submitted source could not be persisted to durable storage"**. Trigger: cumulative submissions exceeding ~1 GB with no pruning. Mitigation now: run the cleanup script on a schedule against the bucket, or raise retention policy work to the next pass. |
| G2 | **The two candidate sandbox images have no automated build/publish path.** `app/services/execution/images.py::build_sandbox_image` exists but has no caller; there is no `modal run` entrypoint. §4.2.1 documents two manual routes. | If the published image is missing `/opt/promptcode-deps/<slug>/node_modules`, Node trusted probes fail **per case with `candidate_error`**, so grading returns **zeros rather than an error**. Trigger: first real submission. Mitigation now: follow §4.2.1 and inspect the first real submission's report instead of trusting `/health`. |
| G3 | `PROMPTCODE_SUPABASE_KEEPALIVE_INTERVAL_SECONDS` is a Settings field and appears in `.env.example`, but the schedule is actually driven by `PROMPTCODE_MODAL_KEEPALIVE_CRON`. | Tuning the interval changes nothing. Harmless today (the default cron is every 6 h, well inside the 7-day pause window). Use `PROMPTCODE_MODAL_KEEPALIVE_CRON` to change the cadence. |
| G4 | `ModalSandboxBackend.cancel()` has no production caller; a client disconnect does not stop a running sandbox early. | Not a correctness or leak risk: every sandbox is bounded by the policy timeout, the Modal `exec` timeout and `finally` termination. It only means cancelled work is not reaped early. Trigger: cost or contention from abandoned runs. |
| G5 | `PROMPTCODE_INTERVIEW_STORAGE_MIN_FREE_BYTES` (default 2 GiB) is compared against the **container's** free disk, and `INTERVIEW_STORAGE_MAX_BYTES` against the container's tree — not the bucket. | If a Modal container reports less than 2 GiB free, workspace create/save/freeze fails closed with 507 before writing. Unverified against real Modal; lower the setting if that happens. |
| G6 | `ensure_workspace` requires a usable `session.challenge_slug` and treats a pre-existing *empty* workspace directory as lost. | Production rows always carry the slug (NOT NULL column) and a real empty workspace is legitimately rebuilt, so impact is limited to callers passing partial session objects. |
| G7 | Postgres-specific paths (advisory locks in `grading_admission.py`, `with_for_update`, the `managed01` migration) are exercised only against SQLite locally. | Verify against the real Supabase project before trusting concurrency behaviour. |


## 6. What is verified vs not verified

### Verified in this repository (commands run locally)

- `backend/modal_app.py` parses (`ast.parse`) and **imports against a stubbed `modal`
  SDK**; `backend/tests/test_deployment_contracts.py` asserts the App name, the
  `@modal.asgi_app()` wiring of `app.main:app`, the grading Function's schedule and
  spawnability, the keep-alive `modal.Cron` + `supabase_keepalive_enabled` gate, the
  image's `requirements.txt`/`app` source inputs, and that the runtime environment
  comes from a Modal Secret rather than literals.
- `vercel.json` is valid JSON. Every rewrite/redirect destination uses the
  `/frontend/...` prefix, because Vercel serves the **repository root** (Root Directory
  stays at the repo root so the root `vercel.json` is read) while the pages live in
  `frontend/`; destination paths of `/interview-*.html` would not resolve. All 31
  `/static/...` references in the HTML were checked to resolve to a real file under
  `frontend/` via the `/static/:path* -> /frontend/:path*` rewrite. The `/api/*`
  destination is an HTTPS `.modal.run` origin with the `/api/:path*` suffix;
  `cleanUrls:false`/`trailingSlash:false` match the `.html` links the frontend actually
  uses (with `cleanUrls:true`, `/challenges.html` would 308 to `/challenges`, which the
  filesystem would then resolve to the legacy `challenges.html` instead of the
  `interview-challenges.html` the backend serves at `/challenges`); the CSP has no
  `'unsafe-inline'` in `script-src` because the frontend has no inline `<script>` blocks
  and no inline event handlers (checked: 0 of each). The only external origins the
  frontend references are `fonts.googleapis.com`, `fonts.gstatic.com`, `esm.sh` and
  `cdn.jsdelivr.net`, and all four are permitted by the CSP directives that use them.
- No frontend file and no `vercel.json` contains a provider, database or signing
  secret.
- `bash scripts/validate-env.sh` passes: every new variable in `.env.example` maps to
  a `Settings` field, and no compose-required variable is missing.
- `backend/tests/test_audit_startup_security.py` proves: modal+supabase production
  config passes; modal configs missing sandbox images, Supabase storage, or a real
  service-role key fail; docker configs still enforce today's rules (runner, HTTPS
  broker, 32-byte broker token, Docker daemon isolation); a placeholder or short
  `grading_signing_key` fails in **both** modes; an unknown execution backend falls
  back to the stricter docker checks.
- The no-Docker-daemon invariant (`/var/run/docker.sock` absent and `DOCKER_HOST`
  unset) is enforced in **every** mode, including modal. It passes trivially in a
  correct Modal container and still rejects a Modal-configured app mistakenly placed
  on a Docker host. (An earlier revision of this lane exempted modal mode; that
  exemption was removed during review as an unnecessary reduction in defense in depth.)
- Read-only confirmation that `statement_cache_size=0` is already set for Postgres in
  `app/db/session.py` and `alembic/env.py`.
- **`backend/requirements.lock` was regenerated** to add `modal==1.6.1` and its
  transitive dependencies, using the command the CI lock check runs:
  ```bash
  cd backend && pip-compile requirements.txt --output-file=requirements.lock \
    --strip-extras --no-header --allow-unsafe
  ```
  Diff is +65/−2, `modal` plus its transitive tree only; no pre-existing pin was
  dropped (`docker==7.1.0`, `fastapi==0.142.2` etc. unchanged).
  **Known pre-existing CI gap, not introduced here:** the committed lock is *not*
  byte-reproducible from `requirements.txt` today, because transitive dependencies have
  released new patch/minor versions since it was generated. This was measured against
  the lock as it stood *before* this migration: a fresh `pip-compile` of the original
  `requirements.txt` already differed from the original lock by 70 lines (e.g. `anyio`
  4.14.2→4.15.1, `certifi` 2026.2.25→2026.7.22). The CI step "Verify
  requirements.lock is up to date" therefore fails independently of this change.
  Reconciling it means bumping ~70 lines of unrelated transitive pins, which was
  deliberately deferred as out of scope for this migration rather than smuggled in
  unnoticed.


### Not verified — requires a real account/deployment

- **`modal deploy` itself has never been run here.** `modal` is not installed in this
  workspace and no Modal token exists. The image API calls
  (`pip_install_from_requirements`, `add_local_dir`, `modal.Secret.from_name`) are
  asserted only against a stub and are pinned to `modal==1.6.1`.
- The actual `.modal.run` URL, the Modal → Supabase network path, TLS to the Supabase
  pooler, and Vercel's rewrite behaviour in production are untested.
- **Grading on Modal (fixed).** `app/workers/interview_grading.py` (`_execute`) selected
  the in-process trusted evaluator only when `PROMPTCODE_EXECUTION_BROKER_URL` was set;
  because a Modal deployment has neither a broker URL nor a sandbox executor URL, every
  claimed job would have failed with *"Trusted grading executor is not configured"*.
  `_in_process_execution()` now also selects the in-process evaluator when
  `execution_backend == "modal"`. Covered by
  `tests/test_managed_storage.py` and exercised end-to-end by
  `tests/test_managed_workflow_integration.py` (submit → durable object → worker drain →
  completed report). The docker/broker branches are unchanged.
- **Submission (coding-challenge) evaluation** stays on the in-request
  `BackgroundTasks` path (`PROMPTCODE_SUBMISSION_INLINE_QUEUE_PROCESSING=true`, the
  default): the HTTP response is returned before the task runs, so it is not a
  synchronous long request. It is *not verified* whether Modal's ASGI shim waits for
  Starlette background tasks before completing the response. Operational note if that
  is ever measured to exceed 150 s: run the existing persistent worker
  (`python -m scripts.run_queue_worker`) wherever a long-lived process is available
  and set `PROMPTCODE_SUBMISSION_INLINE_QUEUE_PROCESSING=false`. `modal_app.py`
  intentionally does not include that always-on worker.
- Free-tier figures and provider policies come from the cited documentation, not from
  measurement in this environment.
- `httpx` is imported directly by `app/main.py` and the workers but is only a
  transitive dependency (via `openai`, 0.28.1 in `requirements.lock`). It is present
  in the Modal image, but it is not pinned as a direct dependency.
