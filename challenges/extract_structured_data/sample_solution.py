"""Sample solution for the 'Extract Structured Claims' challenge.

This demonstrates proper SDK usage and a reasonable approach.
"""

import json
import sys

from promptcode import llm

SYSTEM_PROMPT = """You are a data extraction assistant. Given a noisy insurance claim report,
extract exactly these fields in JSON:
- claimant_name: full name, cleaned of extra whitespace
- date_of_incident: in YYYY-MM-DD format
- injury_category: one of [fracture, burn, laceration, concussion, sprain, internal, other]
- claim_amount: numeric value (float, no currency symbols)

Return ONLY valid JSON. No markdown, no explanation."""


def extract_claim(report_text: str) -> dict:
    response = llm.call(
        model="gpt-4o",
        prompt=f"Extract structured data from this claim report:\n\n{report_text}",
        system=SYSTEM_PROMPT,
        temperature=0,
    )

    try:
        return json.loads(response)
    except json.JSONDecodeError:
        retry = llm.call(
            model="gpt-4o",
            prompt=(
                f"The previous extraction returned invalid JSON. "
                f"Original report:\n\n{report_text}\n\n"
                f"Previous response:\n{response}\n\n"
                f"Return ONLY valid JSON with the required fields."
            ),
            system=SYSTEM_PROMPT,
            temperature=0,
        )
        return json.loads(retry)


def main():
    with open("input.json") as f:
        data = json.load(f)

    claims = data.get("claims", [])
    results = [extract_claim(report) for report in claims]

    print(json.dumps(results, indent=2))


if __name__ == "__main__":
    main()
