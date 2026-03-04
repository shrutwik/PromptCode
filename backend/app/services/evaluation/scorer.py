"""Scoring engine for PromptCode submissions.

Computes six scores (0.0–1.0):
  - accuracy:        how correct the output is vs ground truth (with fuzzy matching)
  - prompt_quality:  how well the candidate engineered their prompts (primary signal)
  - efficiency:      how cheaply / token-efficiently the LLM was used
  - reliability:     consistency across repeated runs
  - orchestration:   penalizes sloppy LLM usage patterns
  - code_quality:    static analysis of error handling, structure, validation
"""

from __future__ import annotations

import difflib
import json
import logging
import re
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Accuracy (with fuzzy / semantic matching)
# ---------------------------------------------------------------------------

def score_accuracy(output: str, ground_truth: str, *, mode: str = "json") -> float:
    if mode == "json":
        return _json_accuracy(output, ground_truth)
    return _text_accuracy(output, ground_truth)


def _json_accuracy(output: str, ground_truth: str) -> float:
    try:
        got = json.loads(output) if isinstance(output, str) else output
        expected = json.loads(ground_truth) if isinstance(ground_truth, str) else ground_truth
    except (json.JSONDecodeError, TypeError):
        return _text_accuracy(str(output), str(ground_truth))

    if isinstance(expected, list) and isinstance(got, list):
        return _list_accuracy(got, expected)
    if isinstance(expected, dict) and isinstance(got, dict):
        return _dict_accuracy(got, expected)
    return 1.0 if got == expected else 0.0


def _dict_accuracy(got: dict, expected: dict) -> float:
    if not expected:
        return 1.0 if not got else 0.0
    total_score = 0.0
    for k, exp_val in expected.items():
        if k not in got:
            continue
        total_score += _fuzzy_field_match(got[k], exp_val, k)
    return total_score / len(expected)


def _list_accuracy(got: list, expected: list) -> float:
    if not expected:
        return 1.0 if not got else 0.0
    correct = 0.0
    used: set[int] = set()
    for exp_item in expected:
        best_score = 0.0
        best_idx = -1
        for j, got_item in enumerate(got):
            if j in used:
                continue
            if isinstance(exp_item, dict) and isinstance(got_item, dict):
                s = _dict_accuracy(got_item, exp_item)
            else:
                s = _fuzzy_field_match(got_item, exp_item)
            if s > best_score:
                best_score = s
                best_idx = j
        if best_idx >= 0 and best_score >= 0.5:
            used.add(best_idx)
            correct += best_score
    return correct / len(expected)


def _fuzzy_field_match(got: Any, expected: Any, field_name: str = "") -> float:
    """Compare two field values with type-aware fuzzy matching."""
    if got is None and expected is None:
        return 1.0
    if got is None or expected is None:
        return 0.0

    if _is_numeric(expected):
        return _match_numeric(got, expected)

    if _looks_like_date(str(expected)) or _looks_like_date(str(got)):
        return _match_date(got, expected)

    if "name" in field_name.lower():
        return _match_name(str(got), str(expected))

    return _match_string(str(got), str(expected))


def _match_numeric(got: Any, expected: Any) -> float:
    """Numeric comparison with tolerance for formatting differences."""
    try:
        got_num = _parse_number(got)
        exp_num = _parse_number(expected)
    except (ValueError, TypeError):
        return 0.0

    if exp_num == 0:
        return 1.0 if got_num == 0 else 0.0

    relative_error = abs(got_num - exp_num) / abs(exp_num)
    if relative_error < 0.001:
        return 1.0
    if relative_error < 0.01:
        return 0.9
    if relative_error < 0.05:
        return 0.7
    return 0.0


def _parse_number(val: Any) -> float:
    if isinstance(val, (int, float)):
        return float(val)
    s = str(val).strip()
    s = re.sub(r"[,$\s]", "", s)
    s = re.sub(r"^(USD|usd)\s*", "", s)
    return float(s)


def _match_date(got: Any, expected: Any) -> float:
    """Date comparison — normalizes both sides to YYYY-MM-DD before comparing."""
    got_date = _parse_date(str(got))
    exp_date = _parse_date(str(expected))

    if got_date is None or exp_date is None:
        return _match_string(str(got), str(expected))

    if got_date == exp_date:
        return 1.0

    delta = abs((got_date - exp_date).days)
    if delta <= 1:
        return 0.8
    return 0.0


_DATE_FORMATS = [
    "%Y-%m-%d",
    "%m/%d/%Y",
    "%m-%d-%Y",
    "%d/%m/%Y",
    "%B %d %Y",
    "%B %d, %Y",
    "%b %d %Y",
    "%b %d, %Y",
    "%b %d,%Y",
    "%d %B %Y",
    "%d %b %Y",
    "%Y/%m/%d",
    "%m/%d/%y",
]


def _parse_date(text: str) -> datetime | None:
    text = re.sub(r"\s+", " ", text.strip())
    text = text.rstrip(".")
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    date_match = re.search(r"(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if date_match:
        try:
            return datetime(
                int(date_match.group(1)),
                int(date_match.group(2)),
                int(date_match.group(3)),
            )
        except ValueError:
            pass
    return None


def _looks_like_date(text: str) -> bool:
    text = text.strip()
    if re.match(r"\d{4}-\d{1,2}-\d{1,2}$", text):
        return True
    if re.match(r"\d{1,2}/\d{1,2}/\d{2,4}$", text):
        return True
    month_names = (
        "january|february|march|april|may|june|july|august|september|"
        "october|november|december|jan|feb|mar|apr|jun|jul|aug|sep|oct|nov|dec"
    )
    if re.search(rf"(?:{month_names})\s+\d{{1,2}}", text, re.IGNORECASE):
        return True
    return False


def _match_name(got: str, expected: str) -> float:
    """Name matching — handles whitespace normalization, middle initials, suffixes."""
    got_clean = _normalize_name(got)
    exp_clean = _normalize_name(expected)

    if got_clean == exp_clean:
        return 1.0

    got_parts = got_clean.split()
    exp_parts = exp_clean.split()

    if len(got_parts) >= 2 and len(exp_parts) >= 2:
        if got_parts[0] == exp_parts[0] and got_parts[-1] == exp_parts[-1]:
            return 0.95

    ratio = difflib.SequenceMatcher(None, got_clean, exp_clean).ratio()
    if ratio >= 0.85:
        return ratio
    return 0.0 if ratio < 0.5 else ratio * 0.5


def _normalize_name(name: str) -> str:
    name = re.sub(r"\s+", " ", name.strip().lower())
    name = re.sub(r"\.$", "", name)
    name = re.sub(r"\s*\.\s*", ". ", name)
    return name


def _match_string(got: str, expected: str) -> float:
    """General string comparison with normalization."""
    got_norm = _normalize(got)
    exp_norm = _normalize(expected)

    if got_norm == exp_norm:
        return 1.0

    if got_norm in exp_norm or exp_norm in got_norm:
        shorter = min(len(got_norm), len(exp_norm))
        longer = max(len(got_norm), len(exp_norm))
        return 0.85 if shorter / longer > 0.7 else 0.6

    ratio = difflib.SequenceMatcher(None, got_norm, exp_norm).ratio()
    if ratio >= 0.9:
        return ratio
    if ratio >= 0.7:
        return ratio * 0.8
    return 0.0


def _normalize(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value).strip().lower())


def _is_numeric(value: Any) -> bool:
    if isinstance(value, (int, float)):
        return True
    try:
        _parse_number(value)
        return True
    except (ValueError, TypeError):
        return False


def _text_accuracy(output: str, ground_truth: str) -> float:
    return difflib.SequenceMatcher(None, output.strip(), ground_truth.strip()).ratio()


# ---------------------------------------------------------------------------
# Efficiency
# ---------------------------------------------------------------------------

def score_efficiency(
    total_tokens: int,
    total_cost_usd: float,
    *,
    token_budget: int = 50_000,
    cost_budget: float = 0.50,
) -> float:
    """Lower usage = higher score. Capped at budget thresholds."""
    token_score = max(0.0, 1.0 - (total_tokens / token_budget))
    cost_score = max(0.0, 1.0 - (total_cost_usd / cost_budget))
    return round((token_score + cost_score) / 2, 4)


# ---------------------------------------------------------------------------
# Reliability
# ---------------------------------------------------------------------------

def score_reliability(accuracies: list[float]) -> float:
    """Consistency across multiple runs.

    Combines mean accuracy with a variance penalty:
    reliability = mean_accuracy * (1 - stddev)
    """
    if not accuracies:
        return 0.0
    n = len(accuracies)
    mean = sum(accuracies) / n
    variance = sum((a - mean) ** 2 for a in accuracies) / n
    stddev = variance ** 0.5
    return round(max(0.0, mean * (1 - stddev)), 4)


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

_PENALTIES = {
    "excessive_retries": 0.15,
    "redundant_calls": 0.10,
    "no_validation": 0.10,
    "no_error_handling": 0.12,
    "bare_except": 0.05,
}


def score_orchestration(
    total_calls: int,
    total_retries: int,
    *,
    expected_calls: int = 3,
    code_analysis: dict[str, Any] | None = None,
) -> float:
    """Penalize sloppy orchestration patterns.

    Now integrates static analysis signals from code_analysis.
    """
    score = 1.0

    if total_retries > total_calls * 0.3:
        score -= _PENALTIES["excessive_retries"]

    if total_calls > expected_calls * 2:
        over_ratio = (total_calls - expected_calls) / expected_calls
        score -= min(_PENALTIES["redundant_calls"] * over_ratio, 0.30)

    if code_analysis:
        analysis = code_analysis.get("analysis", {})
        if not analysis.get("has_try_except", False) and not analysis.get("has_llm_error_handling", False):
            score -= _PENALTIES["no_error_handling"]
        if analysis.get("has_bare_except", False):
            score -= _PENALTIES["bare_except"]
        if not analysis.get("has_json_validation", False):
            score -= _PENALTIES["no_validation"]
    elif total_calls > 0:
        score -= _PENALTIES["no_validation"] * 0.5

    return round(max(0.0, score), 4)


# ---------------------------------------------------------------------------
# Efficiency tradeoff (quality-aware)
# ---------------------------------------------------------------------------

def score_efficiency_tradeoff(
    *,
    total_tokens: int,
    total_cost_usd: float,
    total_latency_ms: float,
    total_calls: int,
    quality_anchor: float,
    budgets: dict[str, float],
) -> float:
    """Score efficiency using a budget frontier + quality gate.

    A submission should not score highly on efficiency if quality is poor,
    even when it uses very few tokens/calls.
    """
    token_budget = max(1.0, float(budgets.get("token_budget", 12_000)))
    cost_budget = max(0.0001, float(budgets.get("cost_budget_usd", 0.20)))
    latency_budget = max(1.0, float(budgets.get("latency_budget_ms", 30_000)))
    call_budget = max(1.0, float(budgets.get("call_budget", 20)))

    token_ratio = total_tokens / token_budget
    cost_ratio = total_cost_usd / cost_budget
    latency_ratio = total_latency_ms / latency_budget
    call_ratio = total_calls / call_budget

    weighted_usage = (
        token_ratio * 0.35
        + cost_ratio * 0.35
        + latency_ratio * 0.20
        + call_ratio * 0.10
    )

    if weighted_usage <= 1.0:
        frontier = 1.0 - (weighted_usage * 0.15)
    else:
        frontier = 1.0 - ((weighted_usage - 1.0) * 0.6)
    frontier = max(0.0, min(1.0, frontier))

    q = max(0.0, min(1.0, quality_anchor))
    quality_gate = max(0.0, min(1.0, (q - 0.2) / 0.6))

    score = frontier * (0.4 + 0.6 * quality_gate)
    return round(max(0.0, min(1.0, score)), 4)


# ---------------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------------

def score_calibration(confidence_points: list[tuple[float, float]]) -> dict[str, Any]:
    """Compute confidence calibration quality from (confidence, outcome) pairs.

    confidence: model confidence in [0, 1]
    outcome: observed correctness in {0, 1}
    """
    if not confidence_points:
        return {
            "score": 0.5,
            "ece": None,
            "brier": None,
            "samples": 0,
            "method": "no_confidence_signals",
        }

    clipped = []
    for conf, outcome in confidence_points:
        c = max(0.0, min(1.0, float(conf)))
        o = 1.0 if float(outcome) >= 0.5 else 0.0
        clipped.append((c, o))

    n = len(clipped)
    brier = sum((c - o) ** 2 for c, o in clipped) / n

    bins = [[] for _ in range(10)]
    for c, o in clipped:
        idx = min(9, int(c * 10))
        bins[idx].append((c, o))

    ece = 0.0
    for bucket in bins:
        if not bucket:
            continue
        avg_conf = sum(c for c, _ in bucket) / len(bucket)
        avg_acc = sum(o for _, o in bucket) / len(bucket)
        ece += (len(bucket) / n) * abs(avg_conf - avg_acc)

    score = 1.0 - min(1.0, (0.65 * brier + 0.35 * ece) * 2.0)
    return {
        "score": round(max(0.0, min(1.0, score)), 4),
        "ece": round(ece, 4),
        "brier": round(brier, 4),
        "samples": n,
        "method": "ece_brier",
    }
