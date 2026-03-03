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

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Health check |
| `GET` | `/api/challenges/` | List all challenges |
| `GET` | `/api/challenges/{id}` | Get challenge details |
| `POST` | `/api/challenges/` | Create a challenge |
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
| **Prompt Quality** | 25% | Clarity, specificity, structure, robustness of prompts (LLM-as-judge) |
| **Accuracy** | 25% | Output correctness vs ground truth (fuzzy matching for dates, names, numbers) |
| **Efficiency** | 15% | Token usage and cost (lower = better) |
| **Reliability** | 15% | Consistency across runs |
| **Orchestration** | 10% | Penalizes retries, redundant calls, missing validation |
| **Code Quality** | 10% | Error handling, structure, validation patterns (AST analysis) |

### Report Format

```json
{
  "accuracy": 0.92,
  "prompt_quality": 0.85,
  "efficiency": 0.71,
  "reliability": 0.88,
  "orchestration": 0.95,
  "code_quality": 0.78,
  "overall": 0.86,
  "cost_usd": 0.14,
  "latency_ms": 4230,
  "llm_calls": 6
}
```

## First Challenge: Extract Structured Claims

Users must parse noisy insurance claim reports and extract:
- `claimant_name`
- `date_of_incident` (YYYY-MM-DD)
- `injury_category` (normalized to: fracture, burn, laceration, concussion, sprain, internal, other)
- `claim_amount` (float)

See `challenges/extract_structured_data/` for the full config and a sample solution.
