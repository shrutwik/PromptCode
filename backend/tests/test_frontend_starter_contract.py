from __future__ import annotations

import re
from pathlib import Path


def _python_starter() -> str:
    html = Path(__file__).resolve().parents[2] / "frontend" / "challenge.html"
    source = html.read_text()
    match = re.search(r"python:\s*`(?P<code>[\s\S]*?)`,\s*javascript:", source)
    assert match, "Python starter block not found in challenge frontend."
    return match.group("code")


def test_python_starter_matches_runtime_contract() -> None:
    starter = _python_starter()

    assert "Path(\"/workspace/input.json\")" in starter
    assert "llm.call(" in starter
    assert "def main()" in starter
    assert 'if __name__ == "__main__":' in starter
    assert "print(" in starter
