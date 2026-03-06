import json
from pathlib import Path

from promptcode import llm

MODEL = "gpt-4o-mini"
SYSTEM_PROMPT = "You are a product feedback analysis assistant. Return only valid JSON."
TASK_FOCUS = "Synthesize review themes, sentiment, risks, and recommended actions into strict JSON."


def _load_context() -> dict:
    return json.loads(Path(__file__).with_name("challenge.json").read_text())


def _load_input() -> dict:
    for candidate in (Path("/workspace/input.json"), Path("input.json")):
        if candidate.exists():
            return json.loads(candidate.read_text())
    return {}


def _ensure_json(raw: str, schema_hint: str) -> str:
    try:
        json.loads(raw)
        return raw
    except json.JSONDecodeError:
        repaired = llm.call(
            model=MODEL,
            system="You repair outputs into strict JSON only.",
            prompt=(
                "Fix this output into valid JSON only.\n\n"
                f"Schema example:\n{schema_hint}\n\n"
                f"Broken output:\n{raw}"
            ),
            temperature=0,
            max_tokens=900,
            retries=1,
        )
        json.loads(repaired)
        return repaired


def main() -> None:
    context = _load_context()
    payload = _load_input()
    schema_hint = json.dumps(context.get("sample_output"), indent=2)
    constraints = json.dumps(context.get("constraints") or {}, indent=2)
    prompt = (
        f"{TASK_FOCUS}\n\n"
        f"Challenge:\n{context.get('description', '').strip()}\n\n"
        f"Constraints:\n{constraints}\n\n"
        f"Output schema example:\n{schema_hint}\n\n"
        f"Input payload:\n{json.dumps(payload, indent=2)}\n\n"
        "Return ONLY valid JSON. Do not add markdown or commentary."
    )
    raw = llm.call(
        model=MODEL,
        system=SYSTEM_PROMPT,
        prompt=prompt,
        temperature=0,
        max_tokens=1800,
        retries=2,
    )
    print(_ensure_json(raw, schema_hint))


if __name__ == "__main__":
    main()
