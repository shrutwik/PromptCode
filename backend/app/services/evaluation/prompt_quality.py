"""Prompt Quality scorer — uses an LLM-as-judge to evaluate how well
the candidate crafted their prompts.

This is the core differentiator for PromptCode: we're not just checking
if the answer is right, we're evaluating *how the candidate talked to the AI*.

Rubric dimensions:
  - Clarity:        Is the prompt unambiguous? Does it avoid vagueness?
  - Specificity:    Does it define the output format, constraints, edge cases?
  - Structure:      Is the prompt organized (system/user separation, sections)?
  - Efficiency:     Does it avoid redundant context or unnecessary verbosity?
  - Robustness:     Does it handle edge cases, instruct on error behavior?
  - Grounding:      Does it provide examples, schemas, or reference data?
"""

from __future__ import annotations

import json
import logging
from typing import Any

import openai
from app.core.model_policy import OPENAI_CHAT_MODELS, resolve_allowed_model

logger = logging.getLogger(__name__)
_ALLOWED_JUDGE_MODELS = set(OPENAI_CHAT_MODELS)
_PROMPT_JUDGE_ERRORS = (
    openai.OpenAIError,
    AttributeError,
    json.JSONDecodeError,
    KeyError,
    IndexError,
    RuntimeError,
    TypeError,
    ValueError,
)

JUDGE_SYSTEM_PROMPT = """You are an expert prompt engineering evaluator for a competitive platform called PromptCode.

You will receive a list of prompts that a candidate sent to an LLM while solving a data extraction challenge. Your job is to evaluate the QUALITY of their prompt engineering — not whether the answer was correct (that's scored separately).

Score each dimension from 0.0 to 1.0:

1. **clarity** — Is the prompt unambiguous? Does it clearly state what the LLM should do? Are instructions precise rather than vague? (e.g., "extract the name" vs "get info")

2. **specificity** — Does the prompt define the exact output format (JSON schema, field names, types)? Does it constrain the response (e.g., "return ONLY valid JSON", "no markdown")?

3. **structure** — Is the prompt well-organized? Does it use system vs user roles effectively? Are there logical sections (task description, constraints, examples)? Is there separation of concerns across multiple prompts?

4. **efficiency** — Is the prompt concise without sacrificing clarity? Does it avoid dumping unnecessary context? Is the token budget used wisely? A 50-token prompt that achieves the same as a 500-token one scores higher.

5. **robustness** — Does the prompt handle edge cases? Does it instruct the LLM on what to do with malformed input, missing fields, or ambiguous data? Does it anticipate failure modes?

6. **grounding** — Does the prompt include examples (few-shot), schemas, reference values, or enumerations? Does it ground the LLM in concrete expectations rather than leaving output open-ended?

Also provide:
- **overall** — A holistic prompt quality score (not a simple average — weight clarity, specificity, and robustness higher as these matter most for real-world AI usage).
- **feedback** — 2-3 sentences of constructive feedback on what the candidate did well and what they could improve.

Return ONLY valid JSON in this exact format:
{
  "clarity": 0.0,
  "specificity": 0.0,
  "structure": 0.0,
  "efficiency": 0.0,
  "robustness": 0.0,
  "grounding": 0.0,
  "overall": 0.0,
  "feedback": "..."
}"""


def score_prompt_quality(
    telemetry_calls: list[dict[str, Any]],
    challenge_description: str,
) -> dict[str, Any]:
    """Evaluate the quality of all prompts the candidate used.

    Returns a dict with per-dimension scores (0.0–1.0), overall score,
    and textual feedback. Falls back to heuristic scoring if the judge
    LLM call fails.
    """
    prompts = _extract_prompts(telemetry_calls)

    if not prompts:
        return _empty_result("No LLM calls were made — nothing to evaluate.")

    try:
        return _judge_with_llm(prompts, challenge_description)
    except _PROMPT_JUDGE_ERRORS:
        logger.exception("LLM judge failed, falling back to heuristic scoring")
        return _heuristic_score(prompts)


def _extract_prompts(calls: list[dict[str, Any]]) -> list[dict[str, str]]:
    """Pull unique (prompt, system_message) pairs from telemetry, deduped."""
    seen: set[str] = set()
    prompts: list[dict[str, str]] = []

    for call in calls:
        prompt_text = call.get("prompt", "")
        system_text = call.get("system", "")
        key = f"{system_text}|||{prompt_text}"
        if key not in seen:
            seen.add(key)
            prompts.append({
                "system": system_text,
                "user": prompt_text,
                "model": call.get("model", "unknown"),
            })
    return prompts


def _judge_with_llm(
    prompts: list[dict[str, str]],
    challenge_description: str,
) -> dict[str, Any]:
    from app.core.config import get_settings
    settings = get_settings()
    api_key = settings.openai_api_key
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not available for judge")

    base_url = settings.openai_base_url.strip() if settings.openai_base_url else ""
    client = openai.OpenAI(api_key=api_key, base_url=base_url or None)
    candidate_models = _resolve_judge_models(settings)

    prompt_listing = ""
    for i, p in enumerate(prompts, 1):
        model_name = p.get("model", "unknown")
        system_text = p.get("system", "")
        user_text = p.get("user", "")
        prompt_listing += f"\n--- Prompt #{i} (model: {model_name}) ---\n"
        if system_text:
            prompt_listing += f"[System]: {system_text}\n"
        prompt_listing += f"[User]: {user_text}\n"

    user_message = (
        f"## Challenge Description\n{challenge_description}\n\n"
        f"## Candidate's Prompts ({len(prompts)} unique prompts)\n"
        f"{prompt_listing}\n\n"
        f"Evaluate the prompt engineering quality across all dimensions."
    )

    last_exc: Exception | None = None
    selected_model = ""
    response = None
    for model in candidate_models:
        try:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": JUDGE_SYSTEM_PROMPT},
                    {"role": "user", "content": user_message},
                ],
                temperature=0.0,
                max_tokens=1024,
            )
            selected_model = model
            break
        except _PROMPT_JUDGE_ERRORS as exc:
            last_exc = exc
            logger.warning("Prompt judge model '%s' failed; trying next fallback", model)
            continue

    if response is None:
        assert last_exc is not None
        raise last_exc

    text = _extract_judge_response_text(response)
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    result = json.loads(text)

    for key in ("clarity", "specificity", "structure", "efficiency",
                "robustness", "grounding", "overall"):
        result[key] = max(0.0, min(1.0, float(result.get(key, 0.0))))

    result.setdefault("feedback", "")
    result["judge_model"] = selected_model
    result["method"] = "llm_judge"
    return result


def _resolve_judge_models(settings: Any) -> list[str]:
    primary = str(getattr(settings, "prompt_judge_model", "") or "").strip()
    fallback = str(getattr(settings, "prompt_judge_fallback_model", "") or "").strip()
    configured_openai_model = str(getattr(settings, "openai_model", "") or "").strip()
    default_model = configured_openai_model or "gpt-4o"

    models: list[str] = []
    raw_seen: set[str] = set()
    canonical_seen: set[str] = set()

    def _append_if_supported(
        raw_model: str,
        *,
        setting_name: str,
        allow_same_canonical: bool = False,
    ) -> str | None:
        canonical_model = resolve_allowed_model(raw_model, _ALLOWED_JUDGE_MODELS)
        if not canonical_model:
            logger.warning("Ignoring unsupported prompt judge %s '%s'", setting_name, raw_model)
            return None
        normalized_raw = raw_model.strip()
        if normalized_raw in raw_seen:
            return canonical_model
        if canonical_model in canonical_seen and not allow_same_canonical:
            return canonical_model
        models.append(raw_model)
        raw_seen.add(normalized_raw)
        canonical_seen.add(canonical_model)
        return canonical_model

    for candidate in primary.split(","):
        raw_model = candidate.strip()
        if not raw_model:
            continue
        _append_if_supported(raw_model, setting_name="model")

    if not models:
        default_canonical = resolve_allowed_model(default_model, _ALLOWED_JUDGE_MODELS)
        if default_canonical:
            models = [default_model]
            raw_seen.add(default_model)
            canonical_seen.add(default_canonical)
        else:
            models = ["gpt-4o"]
            raw_seen.add("gpt-4o")
            canonical_seen.add("gpt-4o")
    elif configured_openai_model:
        default_canonical = resolve_allowed_model(configured_openai_model, _ALLOWED_JUDGE_MODELS)
        if default_canonical and default_canonical in canonical_seen:
            _append_if_supported(
                configured_openai_model,
                setting_name="provider default model",
                allow_same_canonical=True,
            )

    if fallback:
        _append_if_supported(fallback, setting_name="fallback model")
    return models


def _extract_judge_response_text(response: Any) -> str:
    if isinstance(response, str):
        text = response.strip()
        if text.startswith("data:"):
            streamed = _extract_text_from_event_stream(text)
            if streamed:
                return streamed
        return response

    if isinstance(response, dict):
        choices = response.get("choices")
        if not isinstance(choices, list) or not choices:
            raise RuntimeError("Prompt judge returned malformed payload (missing choices).")
        message = choices[0].get("message") or {}
        return str(message.get("content") or "")

    choices = getattr(response, "choices", None)
    if not choices:
        raise RuntimeError("Prompt judge returned malformed payload (missing choices).")

    message = getattr(choices[0], "message", None)
    if isinstance(message, dict):
        return str(message.get("content") or "")
    return str(getattr(message, "content", "") or "")


def _extract_text_from_event_stream(raw: str) -> str:
    chunks: list[str] = []

    for block in raw.split("\n\n"):
        line = block.strip()
        if not line.startswith("data:"):
            continue
        payload = line[5:].strip()
        if not payload or payload == "[DONE]":
            continue
        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            continue

        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            continue
        choice = choices[0] or {}
        message = choice.get("message") or {}
        if isinstance(message, dict) and message.get("content"):
            return str(message.get("content"))
        delta = choice.get("delta") or {}
        if isinstance(delta, dict):
            piece = delta.get("content")
            if piece:
                chunks.append(str(piece))

    return "".join(chunks)


def _heuristic_score(prompts: list[dict[str, str]]) -> dict[str, Any]:
    """Rule-based fallback when the LLM judge is unavailable."""
    scores: dict[str, list[float]] = {
        "clarity": [],
        "specificity": [],
        "structure": [],
        "efficiency": [],
        "robustness": [],
        "grounding": [],
    }

    for p in prompts:
        full_text = f"{p.get('system', '')} {p['user']}".lower()
        length = len(full_text.split())

        scores["clarity"].append(_h_clarity(full_text))
        scores["specificity"].append(_h_specificity(full_text))
        scores["structure"].append(_h_structure(p))
        scores["efficiency"].append(_h_efficiency(full_text, length))
        scores["robustness"].append(_h_robustness(full_text))
        scores["grounding"].append(_h_grounding(full_text))

    result = {}
    for dim, vals in scores.items():
        result[dim] = round(sum(vals) / len(vals), 4) if vals else 0.0

    result["overall"] = round(
        result["clarity"] * 0.20
        + result["specificity"] * 0.25
        + result["structure"] * 0.10
        + result["efficiency"] * 0.10
        + result["robustness"] * 0.20
        + result["grounding"] * 0.15,
        4,
    )
    result["feedback"] = "Scored via heuristic fallback (LLM judge unavailable)."
    result["method"] = "heuristic"
    return result


def _h_clarity(text: str) -> float:
    score = 0.5
    clear_indicators = ["extract", "return", "output", "parse", "convert", "provide"]
    vague_indicators = ["do something", "figure out", "try to", "maybe", "if possible"]
    score += 0.1 * sum(1 for w in clear_indicators if w in text)
    score -= 0.1 * sum(1 for w in vague_indicators if w in text)
    return max(0.0, min(1.0, score))


def _h_specificity(text: str) -> float:
    score = 0.3
    if "json" in text:
        score += 0.2
    if any(f in text for f in ("field", "column", "key", "schema", "format")):
        score += 0.15
    if any(f in text for f in ("only", "exactly", "must", "required", "strictly")):
        score += 0.15
    if any(f in text for f in ("no markdown", "no explanation", "valid json")):
        score += 0.2
    return min(1.0, score)


def _h_structure(prompt: dict[str, str]) -> float:
    score = 0.4
    if prompt.get("system"):
        score += 0.3
    user_text = prompt["user"]
    if "\n" in user_text and len(user_text.split("\n")) > 3:
        score += 0.15
    if any(sep in user_text for sep in ("---", "##", "###", "**", "1.", "- ")):
        score += 0.15
    return min(1.0, score)


def _h_efficiency(text: str, word_count: int) -> float:
    if word_count < 20:
        return 0.3
    if word_count <= 150:
        return 0.9
    if word_count <= 300:
        return 0.7
    return max(0.3, 1.0 - (word_count - 300) / 500)


def _h_robustness(text: str) -> float:
    score = 0.3
    robustness_signals = [
        "if", "missing", "error", "invalid", "malformed", "default",
        "fallback", "unknown", "empty", "null", "none", "edge case",
        "handle", "ignore", "skip",
    ]
    hits = sum(1 for s in robustness_signals if s in text)
    score += min(0.7, hits * 0.12)
    return min(1.0, score)


def _h_grounding(text: str) -> float:
    score = 0.2
    if "example" in text or "e.g." in text or "for instance" in text:
        score += 0.25
    if any(f in text for f in ("one of:", "one of [", "categories:", "allowed values")):
        score += 0.25
    if '{"' in text or "```" in text:
        score += 0.2
    if "yyyy" in text or "mm-dd" in text or any(f in text for f in ("float", "int", "string", "number")):
        score += 0.1
    return min(1.0, score)


def _empty_result(feedback: str) -> dict[str, Any]:
    return {
        "clarity": 0.0,
        "specificity": 0.0,
        "structure": 0.0,
        "efficiency": 0.0,
        "robustness": 0.0,
        "grounding": 0.0,
        "overall": 0.0,
        "feedback": feedback,
        "method": "none",
    }
