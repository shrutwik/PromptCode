"""AI Judge evaluation — uses GPT-4o to evaluate submitted code against
a challenge rubric without requiring Docker sandbox execution.

Flow:
  1. Static analysis: AST-based code quality + pattern detection
  2. Prompt extraction: find all prompt strings embedded in the code
  3. GPT-4o judge call: evaluate accuracy, prompt quality, and overall approach
  4. Scoring: combine AI judge scores with static analysis into final result

The output is an EvaluationResult identical to what the sandbox engine produces,
so the worker and report pipeline remain unchanged.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx

from app.core.config import get_settings
from app.services.evaluation.code_analysis import analyze_code, score_code_quality
from app.services.evaluation.engine import EvaluationResult, SCORE_WEIGHTS, _apply_overall_caps
from app.services.evaluation.prompt_quality import _heuristic_score

logger = logging.getLogger(__name__)
_AI_JUDGE_FAILURES = (
    httpx.HTTPError,
    json.JSONDecodeError,
    KeyError,
    IndexError,
    RuntimeError,
    TypeError,
    ValueError,
)

def _get_judge_model() -> str:
    return get_settings().openai_model or "gpt-4o"


_ENTRYPOINT_LANG = {
    ".py": "python", ".js": "javascript", ".ts": "typescript",
    ".java": "java", ".cpp": "cpp", ".c": "c", ".rs": "rust", ".go": "go",
}

def _lang_from_entrypoint(entrypoint: str) -> str:
    for ext, lang in _ENTRYPOINT_LANG.items():
        if entrypoint.endswith(ext):
            return lang
    return "python"

def _build_judge_prompt(
    code: str,
    challenge_config: dict[str, Any],
    entrypoint: str = "main.py",
) -> str:
    description = challenge_config.get("description", "")
    ground_truth = challenge_config.get("ground_truth", "")
    if isinstance(ground_truth, (list, dict)):
        ground_truth = json.dumps(ground_truth, indent=2)
    inputs = challenge_config.get("inputs", {})
    if isinstance(inputs, dict):
        inputs = json.dumps(inputs, indent=2)[:3000]
    sample_input = challenge_config.get("sample_input", "")
    if isinstance(sample_input, dict):
        sample_input = json.dumps(sample_input, indent=2)
    sample_output = challenge_config.get("sample_output", "")
    if isinstance(sample_output, (dict, list)):
        sample_output = json.dumps(sample_output, indent=2)
    constraints = challenge_config.get("constraints", {})
    processing_rules = challenge_config.get("processing_rules", {})

    skip_conditions = processing_rules.get("skip_conditions", [])
    cross_ref_rules = processing_rules.get("cross_reference_rules", [])
    normalization = processing_rules.get("normalization_rules", {})

    rules_section = ""
    if skip_conditions:
        rules_section += "\n### Skip Conditions (must exclude these from output)\n"
        for i, rule in enumerate(skip_conditions, 1):
            rules_section += f"{i}. {rule}\n"
    if cross_ref_rules:
        rules_section += "\n### Cross-Reference Rules\n"
        for i, rule in enumerate(cross_ref_rules, 1):
            rules_section += f"{i}. {rule}\n"
    if normalization:
        rules_section += "\n### Normalization Rules\n"
        rules_section += json.dumps(normalization, indent=2)[:2000] + "\n"

    return f"""You are an expert code reviewer and AI prompt engineering judge for PromptCode.

## Challenge
{description}

## Constraints
{json.dumps(constraints, indent=2) if constraints else "None specified"}

## Challenge-Specific Processing Rules
{rules_section if rules_section else "None specified"}

## General Processing Rules
{json.dumps(processing_rules, indent=2)[:1500] if processing_rules else "None specified"}

## Sample Input
{sample_input}

## Expected Output Format (sample)
{sample_output}

## Ground Truth (first 2000 chars)
{str(ground_truth)[:2000]}

## Candidate's Code ({entrypoint})
```{_lang_from_entrypoint(entrypoint)}
{code}
```

## Scoring Rubric — Score each dimension from 0.0 to 1.0

**accuracy** — Would this code produce correct output?
- Does it parse inputs correctly and handle the described data formats?
- Would it produce output matching the ground truth structure and values?
- Does it correctly implement all field extractions/classifications?

**prompt_quality** — How well are the LLM prompts engineered?
- Clarity and specificity of instructions to the LLM
- Output format constraints (JSON schema, field names, types)
- Use of examples/few-shot, system vs user message separation
- Does the prompt anticipate failure modes?

**rule_adherence** — Does the code implement the challenge-specific rules?
- Does it handle skip conditions (e.g., excluding VOID/TEST records)?
- Does it implement cross-reference rules (amendments, supplements)?
- Does it apply normalization rules (category mapping, name formatting, amount parsing)?
- Score 0.0 if rules are completely ignored, 1.0 if all rules are addressed in code or prompts

**efficiency** — How token-efficient is the approach?
- Number of LLM calls (fewer is better; batching is ideal)
- Prompt length vs necessity; avoids redundant context
- Estimated cost relative to task complexity

**reliability** — Would this produce consistent results across runs?
- Temperature settings (0 = most consistent)
- Output parsing robustness (try/except around JSON parsing)
- Error handling and retry logic

**orchestration** — How cleanly is the LLM integration structured?
- Separation of concerns, modular design
- Error handling around API calls
- Retry logic, validation of LLM outputs before using them

**code_quality** — How well-structured is the code?
- Function decomposition, readability
- Input/output validation
- Error handling patterns

**edge_case_handling** — How well does the code handle noisy/adversarial input?
- Does the prompt instruct the LLM on malformed input, OCR artifacts, encoding issues?
- Does the code handle missing fields, unexpected formats, empty inputs?
- Does it handle date format variations, currency formatting, name normalization?
- Score based on how many edge cases from the normalization_rules are addressed

Return ONLY valid JSON:
{{
  "accuracy": 0.0,
  "prompt_quality": 0.0,
  "rule_adherence": 0.0,
  "efficiency": 0.0,
  "reliability": 0.0,
  "orchestration": 0.0,
  "code_quality": 0.0,
  "edge_case_handling": 0.0,
  "feedback": "2-3 sentences of constructive feedback",
  "accuracy_reasoning": "Brief explanation of accuracy assessment",
  "rule_adherence_details": "Which rules are addressed and which are missing",
  "estimated_llm_calls": 3,
  "estimated_cost_usd": 0.05
}}"""


PROMPT_QUALITY_JUDGE_PROMPT = """You are an expert prompt engineering evaluator. Given the following prompts extracted from a candidate's code, evaluate their prompt engineering quality.

## Challenge Description
{description}

## Extracted Prompts
{prompts}

Score each dimension 0.0 to 1.0:
- **clarity**: Unambiguous instructions?
- **specificity**: Defined output format, constraints, edge cases?
- **structure**: Well-organized with system/user separation?
- **efficiency**: Concise without sacrificing clarity?
- **robustness**: Handles edge cases and error scenarios?
- **grounding**: Includes examples, schemas, reference values?

Return ONLY valid JSON:
{{
  "clarity": 0.0,
  "specificity": 0.0,
  "structure": 0.0,
  "efficiency": 0.0,
  "robustness": 0.0,
  "grounding": 0.0,
  "overall": 0.0,
  "feedback": "...",
  "method": "llm_judge"
}}"""


def _extract_prompts_from_code(code: str) -> list[dict[str, str]]:
    """Extract LLM prompt strings from source code using regex (language-agnostic)."""
    prompts: list[dict[str, str]] = []

    prompt_patterns = [
        r'(?:prompt|system_message|system|user_message)\s*[:=]\s*(?:f?"""(.*?)"""|f?\'\'\'(.*?)\'\'\'|f?"(.*?)"|f?\'(.*?)\'|`(.*?)`)',
        r'(?:llm[._][Cc]all|LLM\.[Cc]all)\([^)]*(?:prompt|content)\s*[:=]\s*(?:f?"""(.*?)"""|f?\'\'\'(.*?)\'\'\'|f?"(.*?)"|f?\'(.*?)\'|`(.*?)`)',
        r'messages\s*[:=]\s*\[(.*?)\]',
    ]

    for pattern in prompt_patterns:
        for match in re.finditer(pattern, code, re.DOTALL):
            text = next((g for g in match.groups() if g is not None), "")
            if len(text.strip()) > 10:
                prompts.append({"user": text.strip(), "system": "", "model": "unknown"})

    long_str_patterns = [
        r'(?:f?"""(.*?)"""|f?\'\'\'(.*?)\'\'\')',
        r'`([^`]{50,})`',
    ]
    for pattern in long_str_patterns:
        for match in re.finditer(pattern, code, re.DOTALL):
            text = next((g for g in match.groups() if g is not None), "")
            if len(text) > 50 and any(
                kw in text.lower()
                for kw in ["extract", "parse", "return", "json", "output", "classify", "analyze"]
            ):
                already_found = any(p["user"] == text.strip() for p in prompts)
                if not already_found:
                    prompts.append({"user": text.strip(), "system": "", "model": "unknown"})

    return prompts


class JudgeResponse:
    """Wraps an AI judge call result with token/latency metadata."""
    def __init__(self, parsed: dict[str, Any], tokens: int, latency_ms: float):
        self.parsed = parsed
        self.tokens = tokens
        self.latency_ms = latency_ms


def _call_judge(system_prompt: str, user_prompt: str) -> JudgeResponse:
    import time
    import httpx

    settings = get_settings()
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not configured — set a real key in .env")

    base = settings.openai_base_url.rstrip("/") if settings.openai_base_url else "https://api.openai.com/v1"
    url = f"{base}/chat/completions"

    start = time.perf_counter()
    resp = httpx.post(
        url,
        json={
            "model": _get_judge_model(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "temperature": 0.1,
            "max_tokens": 2048,
            "stream": False,
        },
        headers={
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        },
        timeout=60,
    )
    latency_ms = round((time.perf_counter() - start) * 1000, 1)

    if resp.status_code != 200:
        raise RuntimeError(f"AI API returned {resp.status_code}: {resp.text[:300]}")

    data = resp.json()
    text = data["choices"][0]["message"]["content"] or ""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].rsplit("```", 1)[0].strip()

    usage = data.get("usage", {})
    tokens = usage.get("total_tokens", 0)

    return JudgeResponse(json.loads(text), tokens, latency_ms)


def ai_judge_evaluate(
    code: str,
    entrypoint: str,
    challenge_config: dict[str, Any],
) -> EvaluationResult:
    """Evaluate a submission using GPT-4o as the judge instead of sandbox execution."""

    # --- Static code analysis (always works, no LLM needed) ---
    code_analysis_result = analyze_code(code, entrypoint)
    code_quality_result = score_code_quality(code_analysis_result)

    # --- Extract prompts from code for prompt quality scoring ---
    extracted_prompts = _extract_prompts_from_code(code)

    # --- Call GPT-4o to judge the submission ---
    judge_scores: dict[str, Any] = {}
    pq_result: dict[str, Any] = {}

    total_tokens = 0
    total_latency = 0.0
    total_api_calls = 0

    try:
        judge_prompt = _build_judge_prompt(code, challenge_config, entrypoint)
        judge_resp = _call_judge(
            "You are a code evaluation AI. Return only valid JSON.",
            judge_prompt,
        )
        judge_scores = judge_resp.parsed
        total_tokens += judge_resp.tokens
        total_latency += judge_resp.latency_ms
        total_api_calls += 1
        logger.info("AI judge returned scores: %s", {
            k: v for k, v in judge_scores.items()
            if k not in ("feedback", "accuracy_reasoning", "rule_adherence_details")
        })
    except _AI_JUDGE_FAILURES:
        logger.exception("AI judge call failed, using heuristic fallback")
        judge_scores = {
            "accuracy": 0.5,
            "prompt_quality": 0.5,
            "rule_adherence": 0.5,
            "efficiency": 0.5,
            "reliability": 0.5,
            "orchestration": 0.5,
            "code_quality": 0.5,
            "edge_case_handling": 0.5,
            "feedback": "AI judge unavailable — scored via heuristic fallback.",
            "estimated_llm_calls": 3,
            "estimated_cost_usd": 0.05,
        }

    # --- Prompt quality scoring (separate, more detailed) ---
    try:
        if extracted_prompts:
            prompt_listing = ""
            for i, p in enumerate(extracted_prompts, 1):
                prompt_listing += f"\n--- Prompt #{i} ---\n{p['user']}\n"

            pq_prompt = PROMPT_QUALITY_JUDGE_PROMPT.format(
                description=challenge_config.get("description", ""),
                prompts=prompt_listing,
            )
            pq_resp = _call_judge(
                "You are a prompt engineering evaluator. Return only valid JSON.",
                pq_prompt,
            )
            pq_result = pq_resp.parsed
            total_tokens += pq_resp.tokens
            total_latency += pq_resp.latency_ms
            total_api_calls += 1
            for key in ("clarity", "specificity", "structure", "efficiency",
                        "robustness", "grounding", "overall"):
                pq_result[key] = max(0.0, min(1.0, float(pq_result.get(key, 0.0))))
            pq_result.setdefault("method", "llm_judge")
        else:
            pq_result = _heuristic_score([{"user": code[:500], "system": ""}])
            pq_result["feedback"] = "No distinct prompts found in code. Scored based on code content."
    except _AI_JUDGE_FAILURES:
        logger.exception("Prompt quality judge failed, falling back to heuristic")
        pq_result = _heuristic_score(
            extracted_prompts if extracted_prompts else [{"user": code[:500], "system": ""}]
        )

    # --- Clamp and combine scores ---
    def _clamp(v: Any) -> float:
        try:
            return max(0.0, min(1.0, float(v)))
        except (ValueError, TypeError):
            return 0.5

    acc = _clamp(judge_scores.get("accuracy", 0.5))
    pq = _clamp(pq_result.get("overall", judge_scores.get("prompt_quality", 0.5)))
    ra = _clamp(judge_scores.get("rule_adherence", 0.5))
    eff = _clamp(judge_scores.get("efficiency", 0.5))
    rel = _clamp(judge_scores.get("reliability", 0.5))
    orch = _clamp(judge_scores.get("orchestration", 0.5))
    cq_static = _clamp(code_quality_result.get("score", 0.5))
    cq_judge = _clamp(judge_scores.get("code_quality", 0.5))
    cq = round((cq_static + cq_judge) / 2, 4)
    ech = _clamp(judge_scores.get("edge_case_handling", 0.5))
    calibration = 0.5
    calibration_details = {
        "score": calibration,
        "ece": None,
        "brier": None,
        "samples": 0,
        "method": "ai_judge_default",
    }

    # --- Hardcode detection ---
    has_llm_usage = any(
        kw in code.lower()
        for kw in ["llm.call", "openai", "client.chat", "completion", "llm("]
    )
    hardcoded = False
    if not has_llm_usage and acc > 0.3:
        logger.warning("No LLM usage detected — possible hardcoded answer")
        hardcoded = True
        acc = pq = ra = eff = rel = orch = cq = ech = calibration = 0.0
        calibration_details = {
            "score": calibration,
            "ece": None,
            "brier": None,
            "samples": 0,
            "method": "hardcoded_zeroed",
        }

    raw_overall = round(
        acc * SCORE_WEIGHTS["accuracy"]
        + ech * SCORE_WEIGHTS["robustness"]
        + rel * SCORE_WEIGHTS["reliability"]
        + eff * SCORE_WEIGHTS["efficiency"]
        + pq * SCORE_WEIGHTS["prompt_quality"]
        + orch * SCORE_WEIGHTS["orchestration"]
        + calibration * SCORE_WEIGHTS["calibration"],
        4,
    )
    overall, cap_events = _apply_overall_caps(
        raw_overall=raw_overall,
        accuracy=acc,
        rule_adherence=ra,
        anti_gaming_triggered=False,
    )

    estimated_user_calls = int(judge_scores.get("estimated_llm_calls", 1))
    estimated_user_cost = float(judge_scores.get("estimated_cost_usd", 0.02))

    run_records = [
        {
            "run_type": "code_evaluation",
            "run_index": 0,
            "success": True,
            "status": "pass" if acc >= 0.8 and ra >= 0.5 else "fail",
            "accuracy": round(acc, 4),
            "schema_valid": ra >= 0.5,
            "tokens_total": total_tokens,
            "cost_usd": round(estimated_user_cost, 6),
            "latency_ms": round(total_latency, 1),
            "llm_calls": estimated_user_calls,
            "retries": 0,
            "error": None,
            "feedback": judge_scores.get("feedback", ""),
            "accuracy_reasoning": judge_scores.get("accuracy_reasoning", ""),
            "rule_adherence_details": judge_scores.get("rule_adherence_details", ""),
        },
        {
            "run_type": "prompt_quality",
            "run_index": 1,
            "success": True,
            "status": "pass" if pq >= 0.7 else "fail",
            "accuracy": round(pq, 4),  # kept for run-table compatibility
            "schema_valid": True,
            "tokens_total": 0,
            "cost_usd": 0.0,
            "latency_ms": 0.0,
            "llm_calls": 0,
            "retries": 0,
            "error": None,
            "feedback": pq_result.get("feedback", ""),
            "accuracy_reasoning": "",
        },
    ]

    return EvaluationResult(
        accuracy=round(acc, 4),
        prompt_quality=round(pq, 4),
        rule_adherence=round(ra, 4),
        efficiency=round(eff, 4),
        reliability=round(rel, 4),
        orchestration=round(orch, 4),
        code_quality=round(cq, 4),
        edge_case_handling=round(ech, 4),
        calibration=calibration,
        overall=overall,
        cost_usd=estimated_user_cost,
        latency_ms=round(total_latency, 1),
        llm_calls=total_api_calls,
        prompt_tokens=0,
        completion_tokens=0,
        retries=0,
        runs=run_records,
        prompt_quality_details=pq_result,
        code_analysis_details=code_quality_result,
        calibration_details=calibration_details,
        diagnostics=[
            {
                "metric": "summary",
                "severity": "low",
                "message": str(judge_scores.get("feedback", "AI-judge evaluation completed.")),
            }
        ],
        evaluation_config={
            "mode": "ai_judge",
            "judge_model": _get_judge_model(),
            "score_weights": SCORE_WEIGHTS,
            "caps_applied": cap_events,
            "raw_overall": raw_overall,
        },
        confidence_intervals={},
        audit_trail=[],
        evaluation_manifest={},
        hardcoded=hardcoded,
    )
