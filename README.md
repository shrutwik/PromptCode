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
# Edit .env and set your OPENAI_API_KEY
```

### 2. Build the sandbox image

```bash
docker build -t promptcode-sandbox:latest -f docker/Dockerfile.sandbox .
```

### 3. Start the stack

```bash
docker-compose up -d
```

This starts PostgreSQL and the FastAPI backend on `http://localhost:8000`.

The compose stack now includes a `worker` service for resilient async scoring.
If you run the backend outside compose, start the queue worker in a second shell:

```bash
cd backend
python -m scripts.run_queue_worker
```

### 4. Seed the first challenge

```bash
cd backend
pip install -r requirements.txt
python -m scripts.seed_challenge
```

### 5. Verify

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/challenges/
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
uvicorn app.main:app --reload --port 8000
```

The app will create tables on first startup if they don’t exist (`Base.metadata.create_all`). For a clean schema, prefer `alembic upgrade head` after pointing to a new Supabase database.

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

## Evaluation

Each submission is executed **7 times**:
- 5 runs with randomized prompt perturbations (whitespace, casing, formatting noise)
- 2 runs with adversarial inputs (garbage injection, field swaps, encoding noise)

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

Hard gates:
- If `accuracy < 0.40`, overall is capped
- If schema/constraint adherence is weak, overall is capped
- No-LLM hardcoded solutions are disqualified
- Anti-gaming checks penalize extremely low-token low-effort outputs

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

## Growth Backfill

If you added growth/mastery metrics after existing submissions were already stored,
backfill those historical rows and reports:

```bash
cd backend
python -m scripts.backfill_growth_metrics --dry-run
python -m scripts.backfill_growth_metrics
```

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

## Prompt-Judge Calibration Gate

```bash
cd backend
python -m scripts.run_prompt_judge_calibration_gate --mode heuristic --min-samples 20 --min-pearson 0.75 --max-mae 0.25
```
