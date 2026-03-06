"""Per-token pricing table for supported models.

Prices are in USD per token. Update as OpenAI changes pricing.
"""

PRICING: dict[str, dict[str, float]] = {
    "gpt-4o": {
        "prompt": 2.50 / 1_000_000,
        "completion": 10.00 / 1_000_000,
    },
    "gpt-4o-mini": {
        "prompt": 0.15 / 1_000_000,
        "completion": 0.60 / 1_000_000,
    },
}

DEFAULT_PRICING = {
    "prompt": 5.00 / 1_000_000,
    "completion": 15.00 / 1_000_000,
}


def estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    table = PRICING.get(model, DEFAULT_PRICING)
    return (prompt_tokens * table["prompt"]) + (completion_tokens * table["completion"])
