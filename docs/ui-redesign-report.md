# PromptCode UI Redesign — Report (updated final pass)

## UI audit summary
Product surfaces were sparse but uneven: duplicated tokens, weak a11y/motion, cluttered workspace chrome, marketing vs interview type mismatch. Full notes: `docs/ui-audit.md`.

## Design direction
Dark near-black / cool graphite. **Unified chartreuse brand accent** (`#c8f060`) across landing + product; cool blue reserved for AI provenance. IBM Plex Sans + Mono. Expressive landing; focused IDE workspace.

## Design system
- `frontend/css/pc-tokens.css` — chartreuse primary, `--pc-ai`, semantic success/warn/danger, phase tints
- `frontend/css/pc-components.css` — toast, skeleton, grouped palette, score ring, empty/error, resize
- Docs: `docs/design-system.md`, `docs/ui-final-qa.md`

## Motion system
- `frontend/js/pc-motion.js` — higher damping springs; workspace 100–250ms
- Docs: `docs/motion-system.md`

## Final refinement (this pass)
- Brand unification: landing/login/signup/tokens share chartreuse; AI blue separate from test-success green
- Report timeline: proportional scrubber, category marks, keyboard, detail pane, phase mini-map, evidence-linked recovery sequences only when data supports
- Report hierarchy: score hero → what happened → categories → strengths → improvements → recovery → timeline → diff → defend → feedback
- Workspace: grouped ⌘K commands; offline pill; quieter IDE card motion
- Challenge library: status filter + Not started / In progress / Completed tones
- Dashboard: suppress fake trends until ≥3 completions; Continue + Recommended + Recent

## Accessibility
Skip link, `:focus-visible`, dialog roles, aria-live toasts, scrubber slider semantics + arrow keys, Escape closes menus/modals, reduced-motion gates.

## Performance
Not instrumented in CI. Design budget: transform/opacity in workspace; Three lazy + weak-device skip; pause sim on hide. Feel-based QA at 1366/1440/1920 recommended.

## Screens/pages updated
Landing, login, signup, dashboard, challenges library, session workspace, report; shared `interview.css` + JS kit. Auth/onboarding/settings inherit tokens via `interview.css`.

## Known visual limitations
- Native Floating UI not wired to every control yet
- Legacy challenge/leaderboard/playground pages may still use older hardcoded blues in places
- Timeline scrubber was visually coded; full browser scrub QA depends on a live submitted session with events
- Density at 1366/1440/1920 reviewed via CSS/structure, not pixel screenshots in this pass
- No Superdesign workflow — design system is code-owned in `pc-tokens.css`

## Analytics / events
Interview `event_type` strings unchanged. UI category mapping only (`change_reverted` shown under Recovery). Product analytics call sites not duplicated.
