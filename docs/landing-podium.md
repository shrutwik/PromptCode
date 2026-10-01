# Landing sequence — Podium-inspired craft

## What we used

**[podium.global](https://podium.global)** is a sports creative studio site — **not** an npm animation SDK. There is no official “Podium sequence API” or CDN package for embeds.

Their landing craft (observed in production bundles) uses Lenis + GSAP ScrollTrigger. PromptCode originally mirrored that stack, then **removed Lenis** after it proved unreliable here (smooth-wheel overshoot raced through the pin and desynced scrub → jumps / blank frames).

## Final architecture (Option B)

**Native window scroll + GSAP ScrollTrigger `pin` + `scrub: true` + one labeled timeline.**

Boot does **not** wait on `requestAnimationFrame` (background tabs may never paint). Scripts are sync-ordered; init runs immediately (or `setTimeout(0)` if GSAP is late).

| Piece | Choice |
|-------|--------|
| Smooth scroll | **None** (Lenis removed from landing) |
| Pin | `ScrollTrigger` pins `.pc-seq-sticky` (`pin: true`) |
| Track height | CSS `height: auto` — spacer comes from the pin |
| Scrub | `true` (1:1 with scroll; no lag catch-up) |
| Crossfade | Simultaneous `autoAlpha` (no blur / y) so opacity sum ≈ 1 |
| Beat map | Equal timeline units + HUD from `floor(progress × 8)` |

Loaded only from `frontend/index.html`. **Do not** include these scripts on interview/workspace pages.

| Asset | Path |
|-------|------|
| CSS | `/static/css/pc-landing-sequence.css` |
| Driver | `/static/js/pc-landing-sequence.js` |
| CDN | `gsap@3.12.5`, `ScrollTrigger` via jsdelivr |

## Sequence beats (scroll scrub)

Progress HUD (bottom-right) shows `NN% · Beat`.

| % range (approx) | Beat | Story / visual |
|------------------|------|----------------|
| 0–12 | Brand | PromptCode mark bloom |
| 12–25 | Value | “Catch what copilots miss” |
| 25–38 | Library | Practice nav · filters · challenge table row select |
| 38–50 | Workspace | Phase bar · Files · editor · AI Assistant |
| 50–62 | AI | Patch suggestion · Apply pulse |
| 62–75 | Tests | Terminal fail → green pass |
| 75–88 | Report | Score ring · dimension bars |
| 88–100 | CTA | Practice nav · start practice |

### Pace (final)

| Knob | Value | Notes |
|------|-------|--------|
| Pin end | `+= 8 × 1.15 × innerHeight` | ~**1.15 viewport-heights per beat** |
| Timeline | `HOLD 0.72` + `FADE 0.28` per beat | Last beat hold only (no trailing fade) |
| Scrub | `true` | Exact scroll mapping |
| Lenis | **removed** | Was racing the scrubbed pin |

## Root cause (fixed)

Lenis `smoothWheel` + scrubbed CSS-sticky track: a single wheel gesture lerped across thousands of pixels, ScrollTrigger scrub lagged, crossfades (blur + delayed in) left dim/blank frames, and progress jumped to CTA.

## How to tweak

1. **Scroll distance per beat** — `VH_PER_BEAT` in `pc-landing-sequence.js` (raise = slower).
2. **Hold vs fade** — `HOLD` / `FADE` constants in the same file.
3. **Copy / panels** — `.pc-seq-stage` markup in `index.html`.
4. **Reduced motion** — `prefers-reduced-motion: reduce` → stacked static story (no scrub/HUD).

## View

```bash
uvicorn backend.app.main:app --reload --port 8000
```

Open http://127.0.0.1:8000/ (hard-refresh if cached) and scroll the hero sequence.
