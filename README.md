# PromptCode

A LeetCode-style evaluation platform where users solve real-world problems using AI, and are scored on how efficiently and reliably they use LLMs — not just whether they get the right answer.

## Architecture

```
PromptCode/
├── backend/                  # FastAPI application
│   ├── app/
│   │   ├── api/routes/       # REST endpoints
│   │   ├── core/             # Config, settings
│   │   ├── db/               # Database session, base model
│   │   ├── models/           # SQLAlchemy ORM models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── services/
│   │   │   ├── evaluation/   # Scoring engine, perturbation, evaluator
│   │   │   └── sandbox/      # Docker sandbox runner
│   │   └── workers/          # Background evaluation pipeline
│   ├── scripts/              # DB seed scripts
│   └── requirements.txt
├── sdk/                      # promptcode SDK (pip-installable)
│   └── promptcode/
│       ├── client.py         # llm.call() — the tracked LLM wrapper
│       ├── models.py         # Telemetry data classes
│       └── pricing.py        # Per-model cost estimation
├── challenges/               # Challenge definitions + test data
├── docker/                   # Dockerfiles for backend & sandbox
└── docker-compose.yml        # Full local stack
```

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.12+
- An OpenAI API key

### 1. Configure environment

```bash
cp .env.example .env
# Edit .env and set your PROMPTCODE_OPENAI_API_KEY and PROMPTCODE_JWT_SECRET
```

`docker compose` only forwards the `PROMPTCODE_*` settings into the app containers. The unprefixed `OPENAI_API_KEY` remains optional for direct SDK usage outside the platform runtime.

### 2. Start the stack

```bash
docker compose up --build -d
```

This starts PostgreSQL, builds the sandbox image, and launches the sandbox executor, worker, and FastAPI backend on `http://localhost:8000`.
The compose stack always uses the internal Postgres service URL, even if your local `.env` uses SQLite for non-container development.
The local Postgres container is published on host port `5433` by default to avoid colliding with an existing local database on `5432`.
The backend image now includes the static frontend and challenge definitions, so `/` serves the website and challenge seeding works inside the container.
The compose stack includes a dedicated `sandbox-executor` service that owns the Docker socket and shared sandbox workspace path.
Backend and worker submit sandbox runs to that internal executor over HTTP, so they no longer need direct Docker daemon access.
It sets `PROMPTCODE_SANDBOX_NETWORK_MODE=container` so each nested sandbox shares the executor container network namespace and can reach the local relay on `127.0.0.1`.
The executor now exposes `/health`, `/ready`, and `/status` so you can separate process liveness from actual Docker/image readiness.

The compose stack now includes two worker services for conservative multi-user throughput.
It disables in-process submission evaluation in the web container, so queued jobs are handled only by the worker services.
Both the backend and worker containers now run `alembic upgrade head` before starting their main process.
The backend readiness check verifies database connectivity and fails closed if the configured sandbox executor is unreachable.
Worker freshness is enforced separately by the worker container healthcheck and `scripts/check-prod-health.sh`.
The default compose scaling guards are conservative: one submission can fan out at most `PROMPTCODE_EVALUATION_MAX_PARALLEL_SPECS` sandbox runs, the executor accepts at most `PROMPTCODE_SANDBOX_EXECUTOR_MAX_CONCURRENT_RUNS` active runs, and each user can hold at most `PROMPTCODE_SUBMISSION_MAX_OUTSTANDING_JOBS_PER_USER` queued/running evaluations. That user cap does not limit lifetime retries on a challenge; it only limits active jobs at once.
If you run the backend outside compose, start the queue worker in a second shell:

```bash
cd backend
python -m scripts.run_with_migrations python -m scripts.run_queue_worker
```

### 3. Seed the first challenge

```bash
docker compose exec backend python -m scripts.seed_challenge
```

### 4. Verify

```bash
curl http://localhost:8000/health
curl http://localhost:8000/ready
curl http://localhost:8000/api/challenges/
```

`/health` is a liveness check. `/ready` verifies database connectivity and checks the sandbox executor when one is configured.
Worker freshness is monitored separately by the worker healthcheck and `scripts/check-prod-health.sh`.
For a live end-to-end deployment smoke, run:

```bash
cd backend
python -m scripts.run_deploy_smoke --base-url http://127.0.0.1:8000
```

For a direct sandbox-executor smoke, run:

```bash
cd backend
python -m scripts.run_sandbox_executor_smoke --url http://127.0.0.1:8090 --token "$PROMPTCODE_SANDBOX_EXECUTOR_TOKEN"
```

To push beyond the default two-worker topology locally, keep the executor caps in place and scale workers explicitly:

```bash
docker compose up --build -d --scale worker=3 --scale worker-b=1
```

## Using Supabase as the database

You can run the backend against a [Supabase](https://supabase.com) Postgres instance instead of local Docker.

### 1. Create a Supabase project

1. Go to [supabase.com](https://supabase.com) and create a project.
2. In **Project Settings → Database**, copy the **Connection string** (URI format).
3. Replace the scheme: change `postgresql://` to `postgresql+asyncpg://` (required for the async driver).
4. If the URI has a placeholder like `[YOUR-PASSWORD]`, replace it with your database password (same as in the Supabase dashboard).

### 2. Configure `.env`

```bash
# Use your Supabase connection string (with +asyncpg)
PROMPTCODE_DATABASE_URL=postgresql+asyncpg://postgres.[ref]:[password]@aws-0-[region].pooler.supabase.com:5432/postgres

# Required for Supabase (SSL)
PROMPTCODE_DATABASE_SSL_REQUIRE=true

# Optional: custom CA bundle path for TLS verification
PROMPTCODE_DATABASE_SSL_CA_FILE=/etc/ssl/certs/ca-certificates.crt
```

You can use either the **Session pooler** (port 5432) or **Transaction pooler** (port 6543) URI from the Supabase dashboard.

### 3. Run migrations and seed

From the project root (so `.env` is loaded):

```bash
cd backend
pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed_challenge
```

### 4. Start the backend

No need to run PostgreSQL in Docker; start only the FastAPI app:

```bash
cd backend
python -m scripts.run_with_migrations uvicorn app.main:app --reload --port 8000
```

The startup wrapper runs `alembic upgrade head` before launching the app. The FastAPI lifespan still keeps a best-effort `Base.metadata.create_all()` fallback for local resilience, but deploys should rely on Alembic as the schema authority.

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/challenges/` | List all challenges |
| `GET` | `/api/challenges/{id}` | Get challenge details |
| `POST` | `/api/submissions/` | Submit a solution |
| `GET` | `/api/submissions/{id}` | Get submission status |
| `GET` | `/api/submissions/{id}/report` | Get prompt efficiency report |
| `GET` | `/api/submissions/` | List submissions (filter by user/challenge) |
| `GET` | `/api/leaderboard/{challenge_id}` | Get leaderboard |

## SDK Usage

All LLM calls in submitted code **must** go through the SDK:

```python
from promptcode import llm

result = llm.call(
    model="gpt-4o",
    prompt="Extract data from this claim report...",
    temperature=0,
)
```

The SDK automatically logs:
- Token usage (prompt + completion)
- Latency
- Cost estimate
- Full prompt and response text
- Retry attempts

Reports now include `usage_breakdown` with:
- totals (`calls`, `retries`, tokens, cost, latency, averages)
- per-model breakdown (calls/tokens/cost/latency)
- per-run-type breakdown (clean/perturbed/adversarial usage and pass-rate)

Dependency hygiene:
- `backend/requirements.txt` is now pinned to the verified backend dependency set.
- `backend/requirements.lock` mirrors the exact container/runtime versions used for Docker builds.
- `.dockerignore` excludes secrets, tests, and other non-runtime files from the image build context.

## Evaluation

Each submission is evaluated across a deterministic run plan:
- 1+ clean runs (`clean_runs`, default 1)
- 5 perturbed runs (`evaluation_normal_runs`, default 5)
- 2 adversarial runs (`evaluation_adversarial_runs`, default 2)
- Optional hidden clean runs from `config.hidden_tests`

### Scoring (0.0 – 1.0)

| Score | Weight | Measures |
|-------|--------|----------|
| **Accuracy** | 35% | Clean-run correctness vs ground truth |
| **Robustness** | 15% | Pass rate under perturbed and adversarial inputs |
| **Reliability** | 10% | Stability/consistency across repeated runs |
| **Efficiency** | 15% | Cost-latency-token tradeoff, quality-gated |
| **Prompt Design** | 10% | Prompt clarity, specificity, structure, grounding |
| **Orchestration** | 10% | Retry discipline, validation, error handling |
| **Calibration** | 5% | Confidence alignment with observed correctness |

The weighted overall score remains the ranking score. In addition, evaluator now computes an AI-leverage layer for coaching and credibility tracking.

### AI-Leverage Layer (0.0 – 1.0)

- `frontier_navigation_score`: quality achieved relative to token/cost/latency/call usage
- `reliance_calibration_score`: whether model reliance is matched by validation/recovery discipline
- `learning_velocity_score`: iteration-to-iteration improvement efficiency (first attempt defaults to neutral)
- `counterfactual_baseline_overall`: score produced by a naive baseline strategy run in the same sandbox/run plan
- `leverage_gain`: `candidate_overall - counterfactual_baseline_overall`
- `ai_mastery_score`: composite of frontier navigation, reliance calibration, prompt quality, and learning velocity
- `credibility.score`: confidence in evaluation quality (judge mode, sample counts, run depth, run-type diversity, baseline availability, uncertainty, anti-gaming status)
- `learning_effectiveness.coach_hit_rate`: whether previous coaching actions led to metric improvements
- `future_feedback`: behavior-level AI-usage diagnostics plus a measurable 7-day improvement plan (`readiness_score`, `delegation_mode`, prioritized actions, eval protocol)
- `ai_leverage.weight_profile_version`: scoring profile version used for AI mastery/readiness weighting

Hard gates:
- If `accuracy < 0.40`, overall is capped
- If schema/constraint adherence is weak, overall is capped
- No-LLM hardcoded solutions are disqualified
- Anti-gaming checks penalize extremely low-token low-effort outputs

Leaderboard eligibility gates (publish mode):
- Minimum reliability and test-count thresholds
- Prompt judge must run in `llm_judge` mode
- Counterfactual baseline must complete successfully
- `leverage_gain` must be non-negative
- Minimum score credibility threshold

Reproducibility:
- Every run includes deterministic metadata in report (`evaluation_seed`, perturbation config version, per-run seed + perturbation type)
- Report includes `evaluation_manifest` fingerprints (`challenge_fingerprint`, run-plan hash, replay hash)
- Hidden tests are supported via `config.hidden_tests` and excluded from public challenge payloads
- Detailed scoring contract: `docs/SCORING_SPEC.md`

### Report Format

```json
{
  "accuracy": 0.92,
  "edge_case_handling": 0.84,
  "prompt_quality": 0.85,
  "efficiency": 0.71,
  "reliability": 0.88,
  "orchestration": 0.95,
  "calibration": 0.76,
  "overall": 0.86,
  "ai_leverage": {
    "frontier_navigation_score": 0.74,
    "reliance_calibration_score": 0.69,
    "learning_velocity_score": 0.58,
    "counterfactual_baseline_overall": 0.55,
    "leverage_gain": 0.31,
    "ai_mastery_score": 0.69
  },
  "credibility": {
    "score": 0.81,
    "band": "high"
  },
  "learning_effectiveness": {
    "coach_hit_rate": 0.5
  },
  "future_feedback": {
    "readiness_score": 0.68,
    "readiness_band": "medium",
    "delegation_mode": "balanced"
  },
  "cost_usd": 0.14,
  "latency_ms": 4230,
  "llm_calls": 6,
  "tests_passed": 6,
  "tests_total": 8
}
```

## First Challenge: Extract Structured Claims

Users must parse noisy insurance claim reports and extract:
- `claimant_name`
- `date_of_incident` (YYYY-MM-DD)
- `injury_category` (normalized to: fracture, burn, laceration, concussion, sprain, internal, other)
- `claim_amount` (float)

See `challenges/extract_structured_data/` for the full config and a sample solution.

## Prompt Judge Calibration

To keep prompt-quality judging aligned with human ratings, run periodic calibration:

```bash
cd backend
python -m scripts.calibrate_prompt_judge --samples ../docs/prompt_judge_samples.jsonl --mode judge
```

Recommended cadence:
- Weekly during active rubric changes
- Bi-weekly once stable

Each sample should include `reviewed_at` metadata (ISO timestamp).  
Use freshness + calibration gates together:

```bash
cd backend
python -m scripts.run_prompt_judge_dataset_freshness_gate --min-total 24 --min-recent 6 --recent-days 14 --require-reviewed-at
python -m scripts.run_prompt_judge_calibration_gate --mode judge --require-judge-mode --min-samples 20 --min-pearson 0.75 --max-mae 0.25
```

## Growth Backfill

If you added growth/mastery metrics after existing submissions were already stored,
backfill those historical rows and reports:

```bash
cd backend
python -m scripts.backfill_growth_metrics --dry-run
python -m scripts.backfill_growth_metrics
```

## AI Weight Refit

Refit AI mastery/readiness weights from historical submission outcomes:

```bash
cd backend
python -m scripts.refit_ai_weight_profile --dry-run
python -m scripts.refit_ai_weight_profile --output benchmarks/ai_weight_profile.json
```

Optional env override:
- `PROMPTCODE_EVALUATION_WEIGHT_PROFILE_PATH=/absolute/path/to/ai_weight_profile.json`

## Weight Freeze / Approval

Weight profiles are lock-validated by default (`PROMPTCODE_EVALUATION_WEIGHT_PROFILE_ENFORCE_LOCK=true`).
Any profile update requires explicit approval:

```bash
cd backend
python -m scripts.approve_ai_weight_profile \
  --reviewer "your-handle" \
  --calibration-report /path/to/prompt_judge_gate.json
```

This writes `backend/benchmarks/ai_weight_profile.lock.json`.  
Without a matching approved lock, evaluator falls back to static default weights.

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
pytest -q
```

## Reproducibility Gate

```bash
cd backend
python -m scripts.run_reproducibility_gate --repeats 10 --stddev-threshold 0.03
```

## Evaluator Regression Gate

```bash
cd backend
python -m scripts.run_evaluator_regression_gate
```

## Prompt-Judge Calibration Gate

```bash
cd backend
python -m scripts.run_prompt_judge_calibration_gate --mode heuristic --min-samples 20 --min-pearson 0.75 --max-mae 0.25
```

## Challenge Publish Gate

```bash
cd backend
python -m scripts.run_challenge_publish_gate --expected-challenges 10 --min-hidden-cases 2 --min-input-examples 1
```

## Consolidated Release Gates

Non-strict (PR-safe):

```bash
cd backend
python -m scripts.run_release_quality_gates
```

Strict release mode (judge calibration + reviewed sample metadata required):

```bash
cd backend
python -m scripts.run_release_quality_gates --strict
```
