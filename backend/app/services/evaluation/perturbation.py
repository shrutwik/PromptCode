"""Input perturbation strategies for evaluation runs.

Three tiers of perturbation ensure that naive copy-paste prompting fails:

1. Normal runs:     formatting noise (whitespace, casing, minor typos)
2. Structural runs: data-level mutations (extra records, missing fields,
                    contradictory info, reordered fields, decoy data)
3. Adversarial:     aggressive corruption (garbage injection, field swaps,
                    encoding noise, partial data, red herrings)

The key insight: perturbations change the INPUT but NOT the ground truth.
A well-engineered prompt handles all of these gracefully. A copy-pasted
prompt breaks because it can't adapt to structural changes.
"""

from __future__ import annotations

import copy
import random
import re
import string
from typing import Any


def perturb_normal(inputs: dict[str, Any], seed: int) -> dict[str, Any]:
    """Light perturbations: whitespace, casing, minor typos."""
    rng = random.Random(seed)
    return {k: _perturb_value_light(v, rng) for k, v in inputs.items()}


def perturb_adversarial(inputs: dict[str, Any], seed: int) -> dict[str, Any]:
    """Aggressive perturbations: structural mutations + heavy noise."""
    rng = random.Random(seed)
    mutated = _structural_mutation(copy.deepcopy(inputs), rng)
    return {k: _perturb_value_heavy(v, rng) for k, v in mutated.items()}


# ---------------------------------------------------------------------------
# Structural mutations (these break copy-paste solutions)
# ---------------------------------------------------------------------------

_DECOY_NAMES = [
    "INTERNAL NOTE: This record was voided on 2024-01-15. Do not process.",
    "TEST RECORD — IGNORE: QA test entry #4471, not real data.",
    "DUPLICATE ENTRY (see record above) — system error, skip this.",
    "[REDACTED] — Pending legal review. Do not include in output.",
    "TEMPLATE: {field_1} | {field_2} | {field_3} — placeholder only.",
]

_CONTRADICTORY_SNIPPETS = [
    "\n\nCORRECTION: The above amount was revised. See amendment filed separately.\n",
    "\n\nNOTE: Name spelling unverified. May also appear as '{alt_name}'.\n",
    "\n\nUPDATE: Date originally reported incorrectly. Actual date TBD pending review.\n",
    "\n\nWARNING: This record contains unverified information from a third party.\n",
    "\n\nADDENDUM: Category reclassified per internal policy revision 7.2.1.\n",
]


def _structural_mutation(inputs: dict[str, Any], rng: random.Random) -> dict[str, Any]:
    """Apply data-level mutations that require real pipeline logic to handle."""
    for key, value in inputs.items():
        if isinstance(value, list) and len(value) >= 2:
            inputs[key] = _mutate_list(value, rng)
        elif isinstance(value, str) and len(value) > 100:
            inputs[key] = _inject_contradictions(value, rng)
    return inputs


def _mutate_list(items: list[Any], rng: random.Random) -> list[Any]:
    result = list(items)

    if rng.random() < 0.6:
        decoy = rng.choice(_DECOY_NAMES)
        pos = rng.randint(0, len(result))
        result.insert(pos, decoy)

    if rng.random() < 0.4 and len(result) >= 3:
        rng.shuffle(result)

    if rng.random() < 0.3 and len(result) >= 2:
        dup_idx = rng.randint(0, len(result) - 1)
        dup = copy.deepcopy(result[dup_idx])
        if isinstance(dup, str):
            dup = _light_string_noise(dup, rng)
        result.insert(rng.randint(0, len(result)), dup)

    if rng.random() < 0.3:
        for i, item in enumerate(result):
            if isinstance(item, dict) and rng.random() < 0.3:
                keys = list(item.keys())
                if keys:
                    drop_key = rng.choice(keys)
                    result[i] = {k: v for k, v in item.items() if k != drop_key}

    if rng.random() < 0.3:
        for i, item in enumerate(result):
            if isinstance(item, str):
                result[i] = _inject_contradictions(item, rng)

    return result


def _inject_contradictions(text: str, rng: random.Random) -> str:
    if rng.random() < 0.5:
        snippet = rng.choice(_CONTRADICTORY_SNIPPETS)
        snippet = snippet.replace("{alt_name}", _random_name(rng))
        pos = rng.randint(len(text) // 3, max(len(text) - 1, len(text) // 3 + 1))
        text = text[:pos] + snippet + text[pos:]
    return text


def _random_name(rng: random.Random) -> str:
    firsts = ["James", "Maria", "Wei", "Olga", "Ahmed", "Priya", "Carlos"]
    lasts = ["Smith", "Garcia", "Chen", "Williams", "Patel", "Kim", "Santos"]
    return f"{rng.choice(firsts)} {rng.choice(lasts)}"


# ---------------------------------------------------------------------------
# Formatting noise (light)
# ---------------------------------------------------------------------------

def _perturb_value_light(value: Any, rng: random.Random) -> Any:
    if isinstance(value, str):
        return _light_string_noise(value, rng)
    if isinstance(value, list):
        return [_perturb_value_light(v, rng) for v in value]
    if isinstance(value, dict):
        return {k: _perturb_value_light(v, rng) for k, v in value.items()}
    return value


def _light_string_noise(text: str, rng: random.Random) -> str:
    transformations = [
        lambda t: t.replace("  ", " "),
        lambda t: "  " + t + "  ",
        lambda t: t.upper() if rng.random() < 0.2 else t,
        lambda t: re.sub(r"\n{2,}", "\n", t),
        lambda t: t.replace(",", " ,") if rng.random() < 0.15 else t,
        lambda t: t.replace(": ", " :  ") if rng.random() < 0.15 else t,
        lambda t: re.sub(r"(\d{4})-(\d{2})-(\d{2})", _shuffle_date_format(rng), t)
            if rng.random() < 0.3 else t,
    ]
    for fn in rng.sample(transformations, k=rng.randint(1, 3)):
        text = fn(text)
    return text


def _shuffle_date_format(rng: random.Random):
    """Return a re.sub replacement function that changes date format randomly."""
    formats = [
        r"\2/\3/\1",       # MM/DD/YYYY
        r"\3-\2-\1",       # DD-MM-YYYY
        r"\1/\2/\3",       # YYYY/MM/DD
    ]
    fmt = rng.choice(formats)
    def replacer(match: re.Match) -> str:
        y, m, d = match.group(1), match.group(2), match.group(3)
        return fmt.replace(r"\1", y).replace(r"\2", m).replace(r"\3", d)
    return replacer


# ---------------------------------------------------------------------------
# Heavy noise (adversarial)
# ---------------------------------------------------------------------------

def _perturb_value_heavy(value: Any, rng: random.Random) -> Any:
    if isinstance(value, str):
        return _heavy_string_noise(value, rng)
    if isinstance(value, list):
        mutated = [_perturb_value_heavy(v, rng) for v in value]
        if len(mutated) > 1 and rng.random() < 0.3:
            i, j = rng.sample(range(len(mutated)), 2)
            mutated[i], mutated[j] = mutated[j], mutated[i]
        return mutated
    if isinstance(value, dict):
        return {k: _perturb_value_heavy(v, rng) for k, v in value.items()}
    return value


def _heavy_string_noise(text: str, rng: random.Random) -> str:
    text = _light_string_noise(text, rng)

    if rng.random() < 0.4:
        garbage = "".join(rng.choices(string.printable[:62], k=rng.randint(5, 30)))
        pos = rng.randint(0, max(len(text) - 1, 0))
        text = text[:pos] + f" [{garbage}] " + text[pos:]

    if rng.random() < 0.3:
        text = text.replace(".", ".\n\n")

    if rng.random() < 0.2:
        lines = text.split("\n")
        rng.shuffle(lines)
        text = "\n".join(lines)

    if rng.random() < 0.25:
        wrapper = rng.choice([
            f"--- BEGIN FORWARDED MESSAGE ---\n{text}\n--- END FORWARDED MESSAGE ---",
            f"From: system@internal.corp\nSubject: Fwd: Data Record\n\n{text}",
            f"<div class='record-wrapper'>\n{text}\n</div>",
        ])
        text = wrapper

    return text
