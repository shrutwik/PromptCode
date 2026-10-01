# UI Audit — PromptCode Frontend

Date: 2026-09-18  
Scope: all user-facing HTML surfaces under `frontend/`.  
Philosophy target: **Expressive outside the interview. Focused inside the interview.**

## Inventory

| Surface | File | Role |
|---------|------|------|
| Landing | `index.html` | Marketing hero + terminal mock |
| Login / Signup | `login.html`, `signup.html` | Auth |
| Onboarding | `interview-onboarding.html` | Beta welcome |
| Dashboard | `interview-dashboard.html` | Sessions + stats |
| Challenge library | `interview-challenges.html` | Filters + cards |
| Challenge detail | `interview-challenge.html` | Start/resume |
| Workspace | `interview-session.html` | Monaco IDE |
| Report / Defend / Feedback | `interview-report.html` | Score, timeline, debrief |
| Settings / Privacy | `interview-settings.html`, `interview-privacy.html` | Account prefs |
| Legacy | `challenges.html`, `challenge.html`, `profile.html`, `leaderboard.html`, `submission.html` | Pre-interview product |

Shared interview styles: `interview.css` (~14 tokens). Marketing pages duplicate tokens in inline `<style>`.

---

## Cross-cutting findings

### Hierarchy & typography
- Landing uses Instrument Serif + DM Mono; interview pages mix IBM Plex Sans + DM Mono — **two brand voices**.
- Hero titles on dashboard/library use the same `.hero-title` weight as marketing; product pages feel like marketing dumps.
- Workspace chrome is dense but toolbar mixes primary actions with secondary (Benchmark, Relevant) without clear hierarchy.

### Spacing & layout
- No spacing scale tokens; paddings are ad-hoc (6/8/10/12/16/20/28).
- `--radius` is 4px (interview) vs 6px (landing).
- Cards use uneven gaps; library cards rely on inline `style=` margins.

### Color & surfaces
- Strong dark base (`#0a0a09`) + chartreuse accent — good direction, slightly warm graphite.
- Accent used for links, CTAs, and scores — risk of overuse on report.
- Borders are opaque hex; no opacity-based border tokens for calm layering.

### States
- Hover on ghost buttons exists; focus rings largely absent (`:focus-visible` missing).
- Loading = plain “Loading…” text; **no skeletons**.
- Empty states are one muted sentence; no illustration or recovery CTA pattern.
- Error states sparse (login has `role=alert`; interview pages rarely do).

### Clutter
- Workspace top nav packs Save / Tests / Relevant / Benchmark / Review / Submit — violates “top bar: challenge, timer, status, Run, Review, Submit only.”
- Report mixes score, rubric, timeline, defend, and beta feedback without section breathing room.
- Landing hero is relatively clean; below-fold feature sections are text-heavy with weak visuals.

### Motion
- Landing: CSS `pulse` / `blink` only.
- Product: no Motion library, no panel springs, no toast enter/exit.
- **No `prefers-reduced-motion` anywhere.**

### Responsive
- Workspace collapses to stacked panels under 960px; usable but not “Desktop recommended” messaging.
- Marketing has hamburger; interview nav wraps awkwardly on narrow widths.
- Library grid is fine; dashboard stats wrap OK.

### Accessibility
- Interview pages: near-zero `aria-*` / landmarks beyond implicit main.
- Modals lack focus trap / Escape handling / `role=dialog`.
- Monaco + custom tree: keyboard file nav incomplete.
- Contrast of `--muted` (#6b6b65) on `#0a0a09` is marginal for small mono labels.

### Icons
- No shared line-icon system; hamburger is HTML entity `&#9776;`; leaderboard uses emoji.

---

## Per-surface notes

### Landing (`index.html`)
- Brand present; hero message clear (“Engineer AI…”).
- Terminal mock is atmospheric but not an interactive workflow (Repo→…→Submit).
- No magnetic CTAs / workflow node graph / mini interview sim.
- Inline CSS ~500 lines — hard to share with product.

### Login / Signup
- Clean forms; good password a11y hooks on signup.
- Visual language matches landing; not yet tokenized shared CSS.

### Dashboard
- Stat tiles + session list only — missing continue CTA emphasis, sparklines, skills, recommended next.
- Inline styles on cards.

### Challenge library / detail
- Functional filters; cards are sparse (no soft hover lift, no density polish).
- Empty filter state is text-only.

### Workspace
- IDE grid exists (explorer / editor / AI / terminal) — solid skeleton.
- Missing: resizable panels, persist widths, Cmd+K palette, collapse shortcuts, provenance-aware diff polish, authentic pass/fail motion.
- AI panel is chat form — needs context chips + Apply/Reject polish (partially present via apply bar).

### Diff modal
- Basic file list + pre; no provenance highlights; no submit confirmation dialog polish.

### Report
- Score is large accent number — good “strongest surface” seed, but reveal is instant (no restrained motion).
- Timeline is flat list; no scrub/filter/expand recovery linking.
- Defend is sequential Q&A cards — workable mini debrief, needs visual calm.
- Beta feedback present (good).

### Settings / Onboarding / Privacy
- Minimal and clear; onboarding has radial gradient (slightly expressive — OK outside interview).
- Settings lack section structure / toast on save.

---

## Priority backlog (severity → value)

1. **Shared design tokens + type system** (stop inline duplication)
2. **`prefers-reduced-motion` + Motion config**; Floating UI for overlays
3. **Workspace focus**: simplify top bar, panels, palette, a11y modal
4. **Landing expressive**: workflow hero + sim (lazy Three optional)
5. **Dashboard / library density + skeletons**
6. **Report score reveal + timeline scrub**
7. **Toasts, focus rings, empty/error patterns**
8. Legacy pages: align tokens later (lower priority)

---

## Out of scope for visual redesign
- FastAPI, session/scoring APIs, Monaco core, challenge content, auth model.

---

## Implementation status (this pass)

Completed foundation + high-impact polish:

- Design tokens / components: `frontend/css/pc-tokens.css`, `pc-components.css`
- Motion / Floating UI / UI helpers: `frontend/js/pc-motion.js`, `pc-floating.js`, `pc-ui.js`
- Landing hero: `frontend/js/pc-landing-hero.js` (workflow nodes, mini sim, optional Three.js)
- Docs: `docs/design-system.md`, `docs/motion-system.md`
- CSP updated for Monaco + esm.sh (`backend/app/main.py`)
- Workspace: resize panels, palette ⌘K, timer, More menu, toasts, desktop hint
- Dashboard / library / report / landing / login / signup aligned to cool dark system

### Visual QA
Source-inspected only (no local server in this session). Recommend live check at 1366/1440/1920 + mobile marketing.

### Known limitations
- Timeline phase filter only (no scrub playhead)
- Diff CSS provenance classes ready; unified text still mostly plain
- Floating UI helpers shipped; workspace More menu is simple positioned panel
- Legacy challenge/leaderboard/submission pages not fully redesigned
