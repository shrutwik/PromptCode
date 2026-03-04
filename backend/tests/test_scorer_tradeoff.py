from app.services.evaluation.scorer import score_efficiency_tradeoff


def test_efficiency_tradeoff_quality_gate_penalizes_low_quality():
    high_quality = score_efficiency_tradeoff(
        total_tokens=1000,
        total_cost_usd=0.01,
        total_latency_ms=1000,
        total_calls=2,
        quality_anchor=0.9,
        budgets={},
    )
    low_quality = score_efficiency_tradeoff(
        total_tokens=1000,
        total_cost_usd=0.01,
        total_latency_ms=1000,
        total_calls=2,
        quality_anchor=0.2,
        budgets={},
    )
    assert high_quality > low_quality


def test_efficiency_tradeoff_penalizes_over_budget():
    near_budget = score_efficiency_tradeoff(
        total_tokens=9000,
        total_cost_usd=0.15,
        total_latency_ms=20000,
        total_calls=15,
        quality_anchor=0.8,
        budgets={},
    )
    over_budget = score_efficiency_tradeoff(
        total_tokens=60000,
        total_cost_usd=1.2,
        total_latency_ms=180000,
        total_calls=150,
        quality_anchor=0.8,
        budgets={},
    )
    assert near_budget > over_budget
