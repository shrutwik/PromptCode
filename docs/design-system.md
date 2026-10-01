# PromptCode Design System

**Expressive outside. Focused inside.** / **The engineering process is the product.**

Source of truth: `frontend/css/pc-tokens.css` + `frontend/css/pc-components.css` (imported by `interview.css`).

## Direction

Near-black / cool graphite surfaces. **Chartreuse** (`#c8f060`) is the primary PromptCode brand accent — used sparingly in authenticated chrome (logo dot, primary CTAs, focus, score ring). IBM Plex Sans + Mono.

## Accent hierarchy

| Role | Token | Notes |
|------|--------|--------|
| Brand | `--pc-accent` chartreuse | Primary buttons, brand marks — not test success |
| Base | graphite surfaces | `--pc-bg` … `--pc-surface-3` |
| AI / info | `--pc-ai` cool blue `#6ea8ff` | Diff AI provenance, Monaco selection tint |
| Success | `--pc-success` green | Tests passed — never brand accent |
| Warning | `--pc-warn` amber | Recovery, offline |
| Error | `--pc-danger` red | Failures |

Landing, login, signup, and product pages share the same accent, type, button language, and logo mark. Authenticated pages stay quieter (less ambient motion).

## Tokens (summary)

See `pc-tokens.css`: color (incl. phase tints), spacing (4px), radii, shadows, type, motion (workspace 100–250ms), z-index, panels.

Legacy aliases (`--bg`, `--accent`, …) remain for older classnames.

## Components

Buttons, cards, tags (idle/progress/done), toasts, skeletons, command palette (grouped), score ring, empty/error, offline pill, timeline scrubber, resize handles — `pc-components.css` + `interview.css`.

Icons: inline SVG `.pc-icon` stroke currentColor — no emoji.

## JS

| File | Role |
|------|------|
| `js/pc-motion.js` | Motion library + high-damping springs + scoreReveal |
| `js/pc-ui.js` | Toast, grouped palette, panel prefs |
| `js/pc-floating.js` | Floating UI tooltips/menus |
| `js/pc-landing-hero.js` | Marketing workflow + optional Three.js |

## Docs

- `docs/ui-audit.md` — Phase 1 audit
- `docs/motion-system.md` — principles + springs
- `docs/ui-final-qa.md` — final refinement QA
- `docs/ui-redesign-report.md` — redesign + final pass notes
