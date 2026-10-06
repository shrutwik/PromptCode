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
    # Budget and kill switch are checked BEFORE any credential or provider work so
    # a denied reservation can never fall through to a paid call, and so a missing
    # key cannot mask a spending-control failure.
    from app.services.interview.ai_budget import reserve_worker_budget
    reserve_worker_budget([{"role": "system", "content": system_prompt},
                           {"role": "user", "content": user_prompt}], 2048)
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
            **({"thinking": {"type": "disabled"}} if base == "https://api.deepseek.com" else {}),
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
