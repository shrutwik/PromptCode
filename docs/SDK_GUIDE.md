# SDK Guide

`promptcode` is the required interface for any LLM call that should be scored by the platform. The SDK records prompt text, model choice, token usage, latency, retry count, and estimated cost so the evaluator can score both quality and efficiency.

## Minimal Pattern

```python
import json
from promptcode import llm

response = llm.call(
    model="gpt-4o-mini",
    system="You are a strict structured-output assistant.",
    prompt="Return only valid JSON matching the required schema.",
    temperature=0,
    max_tokens=1200,
    retries=2,
)

result = json.loads(response)
print(json.dumps(result))
```

## Baseline Workflow

1. Load `/workspace/input.json` when running in the PromptCode sandbox.
2. Pass the raw payload, challenge description, constraints, and output-schema example into a strict JSON prompt.
3. Validate the first model response with `json.loads`.
4. If parsing fails, make one repair call that only asks for valid JSON.
5. Print the final JSON to stdout.

## Running Locally

- Install the SDK: `pip install -e sdk`
- Set `OPENAI_API_KEY` when running sample solutions directly outside the PromptCode backend.
- Run a sample from its challenge directory so the sibling `challenge.json` file is available.

## Sample Solutions

Each challenge directory now includes a runnable `sample_solution.py` baseline:

- `challenges/bug_report_triage/sample_solution.py`
- `challenges/contract_clause_extraction/sample_solution.py`
- `challenges/email_thread_actions/sample_solution.py`
- `challenges/extract_structured_data/sample_solution.py`
- `challenges/financial_anomaly_detection/sample_solution.py`
- `challenges/legacy_api_migration/sample_solution.py`
- `challenges/nl_to_sql/sample_solution.py`
- `challenges/resume_parsing/sample_solution.py`
- `challenges/review_sentiment_synthesis/sample_solution.py`
- `challenges/support_ticket_routing/sample_solution.py`

These samples are intentionally conservative baselines. They demonstrate correct SDK usage, strict JSON prompting, and one-step repair logic rather than challenge-optimized scoring strategies.
