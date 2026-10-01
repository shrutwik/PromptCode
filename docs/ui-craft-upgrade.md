# UI Craft Upgrade — PromptCode

Elevate interaction quality across the static frontend. **Landing priority:** podium.global–style sequence (see `docs/landing-podium.md`).

## Landing (done — #1)

- **Source of truth:** [podium.global](https://podium.global) craft (Lenis + GSAP ScrollTrigger scrub), not an npm “Podium SDK” (none exists).
- **Files:** `frontend/css/pc-landing-sequence.css`, `frontend/js/pc-landing-sequence.js`, hero markup in `frontend/index.html`.
- **Story beats:** Brand → Value → Library → Workspace → AI → Tests → Report → CTA.
- **A11y:** `prefers-reduced-motion` → stacked static story.
- **Scope:** Landing only — never load sequence scripts in IDE/workspace.

## Inspiration principles (product chrome — next)

| Source | Technique | Apply to |
|--------|-----------|----------|
| Aceternity | Empty CTAs, soft washes | Auth / practice empty states |
| React Bits | Micro-motion 120–240ms | Buttons, cards, nav |
| uiverse | Focus glow, tactile inputs | Shared `.btn` / inputs |

## Remaining craft (after landing)

1. Global tokens + focus rings (`pc-tokens.css`, `pc-components.css`)
2. Auth login/signup polish
3. Practice / library / brief density polish
4. Workspace restrained polish only
5. Report tabs + settings

## View

http://127.0.0.1:8000/ — scroll the first viewport sequence.
