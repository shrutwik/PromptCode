from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMCallRecord:
    """Single tracked LLM invocation."""

    call_id: str
    model: str
    prompt: str
    response: str
    temperature: float
    tokens_prompt: int
    tokens_completion: int
    tokens_total: int
    latency_ms: float
    cost_usd: float
    system: str = ""
    retry_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMSessionLog:
    """Accumulated telemetry for an entire submission run."""

    calls: list[LLMCallRecord] = field(default_factory=list)

    @property
    def total_tokens(self) -> int:
        return sum(c.tokens_total for c in self.calls)

    @property
    def total_cost_usd(self) -> float:
        return sum(c.cost_usd for c in self.calls)

    @property
    def total_latency_ms(self) -> float:
        return sum(c.latency_ms for c in self.calls)

    @property
    def call_count(self) -> int:
        return len(self.calls)

    @property
    def retry_count(self) -> int:
        return sum(1 for c in self.calls if c.retry_index > 0)

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_tokens": self.total_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "total_latency_ms": round(self.total_latency_ms, 2),
            "call_count": self.call_count,
            "retry_count": self.retry_count,
            "calls": [
                {
                    "call_id": c.call_id,
                    "model": c.model,
                    "system": c.system,
                    "prompt": c.prompt,
                    "response": c.response,
                    "temperature": c.temperature,
                    "tokens_prompt": c.tokens_prompt,
                    "tokens_completion": c.tokens_completion,
                    "tokens_total": c.tokens_total,
                    "latency_ms": c.latency_ms,
                    "cost_usd": c.cost_usd,
                    "retry_index": c.retry_index,
                }
                for c in self.calls
            ],
        }
