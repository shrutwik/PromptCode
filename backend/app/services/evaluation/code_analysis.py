"""Static analysis of submitted code to detect orchestration quality signals.

Inspects the candidate's Python source using AST to find:
  - Validation patterns (try/except around JSON parsing, assertions, schema checks)
  - Error handling (try/except around LLM calls, retry logic)
  - Output formatting (json.dumps, csv writing, structured output)
  - Prompt construction patterns (f-strings, templates, string building)
  - Anti-patterns (bare except, no error handling at all, hardcoded values)
"""

from __future__ import annotations

import ast
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CodeAnalysisResult:
    has_try_except: bool = False
    has_json_validation: bool = False
    has_output_formatting: bool = False
    has_llm_error_handling: bool = False
    has_retry_logic: bool = False
    has_input_parsing: bool = False
    has_bare_except: bool = False
    has_prompt_templating: bool = False
    has_schema_validation: bool = False

    function_count: int = 0
    llm_call_count: int = 0
    complexity_signals: list[str] = field(default_factory=list)
    anti_patterns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "has_try_except": self.has_try_except,
            "has_json_validation": self.has_json_validation,
            "has_output_formatting": self.has_output_formatting,
            "has_llm_error_handling": self.has_llm_error_handling,
            "has_retry_logic": self.has_retry_logic,
            "has_input_parsing": self.has_input_parsing,
            "has_bare_except": self.has_bare_except,
            "has_prompt_templating": self.has_prompt_templating,
            "has_schema_validation": self.has_schema_validation,
            "function_count": self.function_count,
            "llm_call_count": self.llm_call_count,
            "anti_patterns": self.anti_patterns,
        }


def analyze_code(source: str, entrypoint: str = "main.py") -> CodeAnalysisResult:
    """Analyze submitted code for quality signals.

    Uses Python AST for .py files; falls back to regex-based heuristic
    analysis for other languages so we never crash on non-Python syntax.
    """
    result = CodeAnalysisResult()

    if entrypoint.endswith(".py"):
        try:
            tree = ast.parse(source)
        except SyntaxError:
            result.anti_patterns.append("syntax_error")
            return result
        visitor = _CodeVisitor(result)
        visitor.visit(tree)
    else:
        _regex_analysis(result, source)

    _detect_anti_patterns(result, source)
    return result


def score_code_quality(analysis: CodeAnalysisResult) -> dict[str, Any]:
    """Convert analysis signals into a code quality score (0.0–1.0)."""

    score = 0.5

    if analysis.has_try_except:
        score += 0.08
    if analysis.has_json_validation:
        score += 0.10
    if analysis.has_output_formatting:
        score += 0.05
    if analysis.has_llm_error_handling:
        score += 0.10
    if analysis.has_input_parsing:
        score += 0.05
    if analysis.has_prompt_templating:
        score += 0.05
    if analysis.has_schema_validation:
        score += 0.07

    if analysis.function_count >= 2:
        score += 0.05
    if analysis.function_count >= 4:
        score += 0.05

    penalty = 0.0
    if analysis.has_bare_except:
        penalty += 0.10
    if "no_error_handling" in analysis.anti_patterns:
        penalty += 0.15
    if "no_functions" in analysis.anti_patterns:
        penalty += 0.08
    if "syntax_error" in analysis.anti_patterns:
        return {
            "score": 0.0,
            "analysis": analysis.to_dict(),
            "penalties": ["syntax_error"],
        }

    final = round(max(0.0, min(1.0, score - penalty)), 4)

    return {
        "score": final,
        "analysis": analysis.to_dict(),
        "penalties": analysis.anti_patterns,
    }


class _CodeVisitor(ast.NodeVisitor):
    def __init__(self, result: CodeAnalysisResult):
        self.result = result
        self._in_try = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.result.function_count += 1
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.result.function_count += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:
        self.result.has_try_except = True

        for handler in node.handlers:
            if handler.type is None:
                self.result.has_bare_except = True

            handler_name = _get_exception_name(handler)
            if handler_name in ("JSONDecodeError", "json.JSONDecodeError", "ValueError"):
                self.result.has_json_validation = True
            if handler_name in ("APIError", "openai.APIError", "Exception", "RuntimeError"):
                self.result.has_llm_error_handling = True

        prev = self._in_try
        self._in_try = True
        self.generic_visit(node)
        self._in_try = prev

    def visit_Call(self, node: ast.Call) -> None:
        call_name = _get_call_name(node)

        if call_name in ("llm.call", "self.llm.call"):
            self.result.llm_call_count += 1
            if self._in_try:
                self.result.has_llm_error_handling = True

        if call_name in ("json.loads", "json.load"):
            self.result.has_input_parsing = True
            if self._in_try:
                self.result.has_json_validation = True

        if call_name in ("json.dumps", "json.dump", "csv.writer", "csv.DictWriter"):
            self.result.has_output_formatting = True

        if call_name in ("pydantic.BaseModel", "TypeAdapter", "model_validate"):
            self.result.has_schema_validation = True

        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = _get_call_name(child)
                if name in ("llm.call",) and isinstance(node.iter, (ast.Call, ast.Name)):
                    self.result.has_retry_logic = True
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:
        for child in ast.walk(node):
            if isinstance(child, ast.Call):
                name = _get_call_name(child)
                if name in ("llm.call",):
                    self.result.has_retry_logic = True
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr) -> None:
        self.result.has_prompt_templating = True
        self.generic_visit(node)


def _get_call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute):
        if isinstance(node.func.value, ast.Name):
            return f"{node.func.value.id}.{node.func.attr}"
        if isinstance(node.func.value, ast.Attribute):
            if isinstance(node.func.value.value, ast.Name):
                return f"{node.func.value.value.id}.{node.func.value.attr}.{node.func.attr}"
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def _get_exception_name(handler: ast.ExceptHandler) -> str:
    if handler.type is None:
        return ""
    if isinstance(handler.type, ast.Name):
        return handler.type.id
    if isinstance(handler.type, ast.Attribute):
        if isinstance(handler.type.value, ast.Name):
            return f"{handler.type.value.id}.{handler.type.attr}"
    return ""


def _regex_analysis(result: CodeAnalysisResult, source: str) -> None:
    """Language-agnostic heuristic analysis using regex patterns."""
    import re as _re

    fn_patterns = [
        r'\bfunction\s+\w+',       # JS/TS
        r'\bfn\s+\w+',             # Rust
        r'\bfunc\s+\w+',           # Go
        r'\bdef\s+\w+',            # Python (unlikely path)
        r'(public|private|protected)\s+\w+\s+\w+\s*\(', # Java/C#
    ]
    result.function_count = sum(
        len(_re.findall(p, source)) for p in fn_patterns
    )

    if _re.search(r'\bllm[._]call|llm[._]Call|LLM\.call|LLM\.Call', source):
        result.llm_call_count = len(
            _re.findall(r'\bllm[._][Cc]all|LLM\.[Cc]all', source)
        )

    try_patterns = [
        r'\btry\s*\{',             # JS/TS/Java/Go
        r'\btry\s*:',              # Python
        r'\bmatch\b.*\bErr\b',     # Rust
        r'\bif\s+err\s*!=\s*nil',  # Go
    ]
    result.has_try_except = any(
        _re.search(p, source) for p in try_patterns
    )

    result.has_json_validation = bool(
        _re.search(r'JSON\.parse|json\.Unmarshal|serde_json|json\.loads|json_decode|JSONDecodeError', source)
    )
    result.has_output_formatting = bool(
        _re.search(r'JSON\.stringify|json\.Marshal|serde_json::to_string|json\.dumps|json_encode', source)
    )
    result.has_input_parsing = result.has_json_validation
    result.has_prompt_templating = bool(
        _re.search(r'`[^`]*\$\{|f"|f\'|format!|fmt\.Sprintf|String\.format', source)
    )

    if _re.search(r'\bcatch\s*\(|except\b', source):
        if _re.search(r'\bcatch\s*\(\s*\)', source):
            result.has_bare_except = True
        result.has_llm_error_handling = result.has_try_except

    result.has_retry_logic = bool(
        _re.search(r'\bretry|for\s*\(.*attempt|while\s*\(.*attempt|for\s+_\s+in\s+range', source)
    )
    result.has_schema_validation = bool(
        _re.search(r'zod\.|z\.\w+|Joi\.|@Valid|#\[validate|validator', source)
    )


def _detect_anti_patterns(result: CodeAnalysisResult, source: str) -> None:
    if not result.has_try_except and result.llm_call_count > 0:
        result.anti_patterns.append("no_error_handling")

    if result.function_count == 0:
        result.anti_patterns.append("no_functions")

    if result.has_bare_except:
        result.anti_patterns.append("bare_except")

    if "while True" in source and "break" not in source:
        result.anti_patterns.append("infinite_loop_risk")
