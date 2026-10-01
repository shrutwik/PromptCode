# UI refactor — unified design system (Sep 2026)

Screenshots: `.qa-screenshots/refactor-before/` (audit) and `.qa-screenshots/refactor-after/` (result).
Capture script: Playwright-core + system Chrome, 1440x900 for every page, 390x844 for public pages,
real disposable account → session started → tests run → submitted. Console errors / 4xx logged to `_log.json`.

## Audit (before)

### Served routes
| Route | File | Surface |
|---|---|---|
| `/`, `/index.html` | index.html | public landing (GSAP scroll sequence) |
| `/login.html`, `/signup.html` | login/signup.html | public auth |
| `/onboarding(.html)` | interview-onboarding.html | post-signup |
| `/privacy(.html)` | interview-privacy.html | public |
| `/leaderboard.html` | leaderboard.html | public (legacy prompt product) |
| `/playground.html` | playground.html | redirect stub |
| `/dashboard` | interview-dashboard.html | app — Practice / Progress |
| `/challenges` | interview-challenges.html | app — library |
| `/challenges/{slug}` | interview-challenge.html | app — brief |
| `/session/{id}` | interview-session.html | app — IDE workspace |
| `/session/{id}/report` | interview-report.html | app — report |
| `/settings(.html)` | interview-settings.html | app — settings |
| `/challenges.html`, `/challenge.html`, `/submission.html`, `/profile.html` | legacy prompt-challenge product | app (legacy) |
| `/login`, `/practice` | — | **404** |

### P0 — broken flows
1. **Every interview app page renders empty** (dashboard, library, brief, session, report, settings).
   The CSP (`backend/app/main.py`) whitelists inline scripts by sha256 hash, computed once and `lru_cache`d at
   server start. Each UI pass edited inline `<script>` blocks, so the running server blocks them:
   `Executing inline script violates … script-src`. Dashboard shows headings with no data, library is a
   permanent skeleton, workspace stays "Loading scenario…", report stays "Loading report…".
   (`dashboard_1440.png`, `library_1440.png`, `session_1440.png`, `report_1440.png`)
2. Inline `onclick=` attributes in dashboard/report are blocked by `script-src-attr 'none'`.
3. Onboarding throws `TypeError: Cannot read properties of undefined (reading 'classList')` after signup.
4. Logged-in users hitting `/`, `/login.html`, `/signup.html` are auto-redirected to the **legacy**
   `/challenges.html` (different product, different styling) instead of Practice (`/dashboard`);
   `login.js` also ignores the `?next=` param that `InterviewAPI.requireAuth` sets.
5. `/login` and `/practice` 404.

### P1 — inconsistent system (stacked passes)
6. Three unrelated visual languages: interview pages (IBM Plex, `pc-tokens`), landing (IBM Plex, its own
   inline `:root` + 300-line `<style>`), login/signup/leaderboard/legacy pages (DM Mono + Instrument Serif,
   own inline `:root`). Headings render in a serif on auth + leaderboard, monospace body text everywhere else.
7. Four different navs: landing nav, auth mini-header, legacy product nav (challenges/leaderboard),
   interview `mountAppNav`. Onboarding + privacy have **no nav at all**. Footer only on landing.
8. Duplicate/conflicting CSS in `interview.css` (two passes appended): `.page`, `.filters`, `.stat-grid`,
   `.stat`, `.dash-continue`, `.apply-bar`, `.chat-msg` are each defined twice with different values.
   Each legacy page re-declares its own `.btn`, nav, inputs, tokens (~1,700 lines of inline CSS total).
9. Dead assets: `js/pc-floating.js`, `js/pc-landing-hero.js`, `js/pc-motion.js` are not referenced by any page.
10. Buttons: 4 different heights/radii/case styles (`sign in →` lowercase mono vs `Submit` sans).

### P2 — layout / polish defects
11. Landing: fixed "100% · CTA" progress pill stays on screen after the sequence and overlaps the footer
    copyright (`landing_1440_s7.png`); large empty gap under the "Prove you can engineer with AI" CTA beat.
12. Signup @390: page title clipped under the fixed header (`signup_390.png`).
13. Auth errors: signup shows validation/API errors by rewriting the submit button's label for 2–3s
    (no inline error, not announced to screen readers). OAuth buttons are placeholders that go to signup.
14. Leaderboard: "No entries yet" printed twice (hero + table); selector floats unaligned above the table.
15. Dashboard: "Recent sessions" / "Progress" headings with no empty state; nav "Account" button has no
    identity; no skeletons while loading.
16. Workspace: Monaco codicon font blocked by CSP `font-src` (icons in editor widgets render as boxes).
17. Motion: only ad-hoc hover transitions; no page enter, no list reveal, no tab indicator, toasts only
    fade in. Reduced-motion handled only by zeroing three duration tokens.

## Design system (after)

One token file + one component stylesheet + one shell script. Everything else is page layout only.

| File | Owns |
|---|---|
| `frontend/css/pc-tokens.css` | color, spacing, radii, type scale, **motion tokens**, z-index, panel sizes, legacy aliases (`--bg`, `--accent`, `--surface2`, `--font-mono`…) |
| `frontend/css/pc-components.css` | base reset/typography/focus, `.btn` (+`-primary/-secondary/-ghost/-quiet/-danger/-sm/-lg/-icon/-block`), forms (`.pc-field`, `.pc-input`, `.pc-check`, `.pc-alert`, `.pc-field-error`), `.filters`, `.tag`/`.badge` + `data-tone`, `.pc-panel`/`.card`, `.stat-grid`, `.pc-table`/`.challenge-table`, `.pc-tabs` (+sliding `.pc-tabs-ind`), `.pc-segmented`, `.pc-bar`, `.pc-score-ring`, app nav `.nav`, public `.pc-header`/`.pc-footer`, `.pc-auth` layout, `.modal`/`.pc-drawer`, `.pc-toast`, `.pc-skeleton`, `.pc-empty`, `.pc-error`, palette, kbd, resize handles, motion utilities |
| `frontend/js/pc-ui.js` | `PCUI.mountPublicHeader/Footer` (auto on `[data-pc-header]`/`[data-pc-footer]`), `PCUI.mountAppNav` (auto on `nav.nav`), account menu (Settings / Feedback / Log out), `PCUI.tabs(el)` (auto on `[data-pc-tabs]`), `PCUI.toast`, `PCUI.skeletonRows/emptyState/bar/esc`, command palette, panel size prefs, `[data-pc-reload]` |
| `frontend/interview.css` | interview app page layouts + IDE workspace only |
| `frontend/css/pc-landing-sequence.css` | landing only |
| `frontend/js/pages/*.js` | page scripts (externalized from inline `<script>` so the hash-based CSP can never go stale again) |

### Standard `<head>` (every page, in this order)
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,500;1,600&display=swap">
<link rel="stylesheet" href="/static/css/pc-tokens.css?v=20260922">
<link rel="stylesheet" href="/static/css/pc-components.css?v=20260922">
<!-- then ONE page stylesheet: interview.css | pc-landing-sequence.css | a small inline <style> for layout only -->
```
`<script src="/static/js/pc-ui.js?v=20260922"></script>` on every page (after `api.js`/`interview-api.js`).

### Shells
- Public pages: `<body class="pc-public">` → `<header data-pc-header></header>` … `<main class="pc-main">` … `<footer data-pc-footer></footer>`.
- App pages: `<nav class="nav" aria-label="App"><a class="nav-brand" href="/dashboard">PromptCode</a></nav>` → `<main class="page">`.
- Workspace: `<body class="ide-body">` with its own top bar (no app nav).

### Motion
Tokens: `--pc-dur-instant 80 / fast 120 / normal 180 / slow 240 / page 280 / fill 720 / express 520 / cinematic 900ms`,
`--pc-ease-out` (enter), `--pc-ease-in` (exit), `--pc-ease-in-out`, `--pc-ease-soft` (fills), `--pc-ease-press`, `--pc-stagger 35ms`, `--pc-enter-y 6px`.
- Page enter: `.page`, `.pc-main`, `.pc-auth-card` fade + 6px rise (280ms).
- Lists/tables: add `data-stagger` to the container (`tbody`, grid) → children reveal 35ms apart (first 12).
- Hover/press: `.btn` 1px lift / 0.98 press; interactive cards lift 2px; table rows tint.
- Tabs: `.pc-tabs` indicator slides (180ms). Nav active underline grows in.
- Menus/modals/drawers/toasts: scale-fade in, toasts slide out (`.is-leaving`).
- Skeleton shimmer while loading (`PCUI.skeletonRows(n)`); bars fill from 0 (`PCUI.bar(pct, tone, delay)`), score ring sweeps (`@property --pc-ring-p`).
- `prefers-reduced-motion: reduce`: duration tokens → 1ms, enter offset 0, global animation/transition clamp, shimmer off. Landing GSAP sequence has its own reduced-motion path.
