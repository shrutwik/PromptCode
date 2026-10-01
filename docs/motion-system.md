# PromptCode Motion System

## Principles

1. Motion clarifies state — never decorates by default.
2. Expressive on marketing; calm in the interview workspace.
3. Prefer transform/opacity; avoid layout thrash.
4. **Mandatory** `prefers-reduced-motion` support.
5. Pause off-screen (IntersectionObserver / visibility); no continuous spam.
6. Workspace durations stay **100–250ms** with **high damping** — never compete with Monaco.

## Library

[Motion One](https://motion.dev) via `esm.sh`, wrapped in `frontend/js/pc-motion.js`.

Floating UI (`@floating-ui/dom`) for tooltips/menus: `frontend/js/pc-floating.js`.

Shared toast/palette helpers (WAAPI fallback): `frontend/js/pc-ui.js`.

Landing-only hero: `frontend/js/pc-landing-hero.js` (workflow springs + optional lazy Three.js wireframe). **Never** load Three.js in the workspace.

## Config (`PC_MOTION` / springs)

| Name | Intent |
|------|--------|
| `springSoft` | Card settle / gentle hover (library only) |
| `springSnappy` | Buttons / controls |
| `springPanel` | Panel release settle (high damping, tiny overshoot) |
| `fadeFast` / `fadeNormal` | Opacity transitions |
| `staggerSmall` | 40ms list reveals |

Workspace CSS tokens: `--pc-dur-fast` 120ms, `--pc-dur-normal` 180ms, `--pc-dur-slow` 240ms. Timeline playhead uses linear short transitions (no bounce).

## Physics targets

- Panel settle after resize release
- Drawer/modal: small overshoot, high damping
- Card hover: −2px on marketing/library only — disabled under `.ide-body`
- Button press: scale 0.98 → 1.0
- Score reveal: count-up ≤700ms, no confetti

## Reduced motion

`prefersReducedMotion()` short-circuits springs to instant opacity/position. CSS tokens zero durations under the media query. Landing skips Three.js and floating node loops. Timeline scrub uses `behavior: auto` when reduced.

## Performance

- Animate `transform` / `opacity` only when possible
- rAF loops cancel when canvas leaves viewport
- Weak-device heuristic skips Three.js (cores/memory/narrow viewport)
- Goal: 60fps on typical laptop; if laggy, remove effect — do not add layers
