from __future__ import annotations

from collections.abc import Iterable

OPENAI_CHAT_MODELS: tuple[str, ...] = (
    "gpt-4o",
    "gpt-4o-mini",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
)
_MODEL_PREFIX_SEPARATORS: tuple[str, ...] = ("/", ":", ".")


def resolve_allowed_model(model: str | None, allowed_models: Iterable[str]) -> str | None:
    """Resolve provider-prefixed model aliases to an allowed canonical model id."""
    raw_model = str(model or "").strip()
    if not raw_model:
        return None

    canonical_by_lower = {m.lower(): m for m in allowed_models}
    lowered = raw_model.lower()

    direct = canonical_by_lower.get(lowered)
    if direct:
        return direct

    for sep in _MODEL_PREFIX_SEPARATORS:
        for canonical_lower, canonical in canonical_by_lower.items():
            if lowered.endswith(f"{sep}{canonical_lower}"):
                return canonical

    return None
