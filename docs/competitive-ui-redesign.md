# Competitive UI Redesign — PromptCode

UI/UX only. No backend, API, scoring, auth, or event-schema changes.

## Current UI

| Surface | File | Today |
|---------|------|--------|
| Landing | `index.html` | Expressive marketing hero |
| Auth | `login.html`, `signup.html` | Chartreuse forms |
| Practice | `interview-dashboard.html` | Sparse “Dashboard”; stats + cards |
| Library | `interview-challenges.html` | Card grid; type/stack/status filters |
| Brief | `interview-challenge.html` | Marketing hero + serif README |
| Workspace | `interview-session.html` | IDE: files \| editor \| AI; terminal; resize |
| Report | `interview-report.html` | Long single scroll; scrubber + defend |
| Settings | `interview-settings.html` | Minimal form, no product nav |
| Tokens | `css/pc-tokens.css` | Graphite + restrained chartreuse |

Shared: `interview.css`, `pc-components.css`, `js/pc-ui.js`.

## Problems

1. Nav mixes marketing labels (Dashboard/About) — no Practice / Progress / account menu.
2. Library is card-heavy; hard to scan at list density.
3. Brief feels promotional (serif H2), not an assessment briefing.
4. Practice home overloads stats before Continue / Recommended.
5. Report is one long page — no Overview | Timeline | Code | Defend tabs.
6. Workspace missing subtle Plan/Build/Review phase; ticket buried in README file.
7. AI panel uses brand accent for AI labels (should be info blue).
8. Panel defaults slightly short of target density (term 160 vs 180–240).
9. Inconsistent account chrome (Settings lacks product nav / Feedback / Logout pattern).

## Competitive inspiration (principles, not clones)

From mature coding/interview platforms (LeetCode / HackerRank / CodeSignal class):

- Dense, scannable lists and toolbars over marketing cards
- Stable product chrome: Practice · Challenges · Progress + account
- Assessment briefings: meta tags, time, stacks, clear primary CTA
- IDE-first workspace: thin separators, resizable panes, quiet chrome
- Compact AI assistant integrated beside editor (not a chatbot landing)
- Report as structured review tabs with timeline scrubbing
- Restraint: accent for CTA/selection only; semantic colors for status

Do **not** copy logos, exact layouts, colors, type, or component shapes.

## New visual language

- **Surfaces:** Dark graphite bg; lighter panels; thin borders; radius 6–10px (tighter in IDE)
- **Type:** Off-white primary, muted secondary; page 24–30 / section 16–20 / body 14–15 / meta 12–13 / code 13–14
- **Accent:** Chartreuse only for CTA, selected, focus
- **Semantic:** success green, warn amber, error red, info/AI blue
- **Lists:** Tables for library; cards only for Continue / paths / feedback
- **Motion:** 120–220ms; respect `prefers-reduced-motion`
- **Workspace density:** explorer 220–260, AI 300–380, terminal 180–240 (defaults mid-range)
- **Landing:** May stay expressive; authenticated product denser/restrained
- **A11y:** focus rings, keyboard scrubber/tabs, labeled controls, contrast

## Page-by-page changes

1. **Global tokens** — Panel defaults, type scale, product density vars
2. **Navigation** — Practice, Challenges, Progress; account: Settings, Feedback, Logout (no Leaderboard in interview — private practice)
3. **Practice home** — Continue + Recommended + paths + recent; progress deferred to Progress section
4. **Library** — Compact table + toolbar: Search, Difficulty, Domain, Stack, Status
5. **Brief** — Assessment layout; Start Interview CTA; ticket body
6. **Workspace** — Phase strip; ticket collapsible; IDE tab accent; density defaults
7. **AI panel** — Compact messages; context chips; patch apply bar; AI blue labels
8. **Terminal** — Dense meta + log (existing, tightened)
9. **Submit** — Keep compact modal (existing)
10. **Report** — Tabs: Overview | Timeline | Code | Defend (+ feedback on Overview)
11. **Timeline** — Scrubber + compact list (existing, under Timeline tab)
12. **Progress** — Stats / skills / trends on Practice page `#progress`
13. **Responsive** — Desktop-first workspace hint; public pages mobile-ok

## Components to update

- `pc-tokens.css` — density / type / panel defaults
- `pc-components.css` — tabs, table, account menu (as needed)
- `interview.css` — nav active, library table, brief, phase bar, report tabs, ticket
- `pc-ui.js` — `mountAppNav()` shared chrome
- Interview HTML pages listed above

## Constraints / deferrals

- No API or scoring changes
- Legacy marketing pages (`challenges.html`, `leaderboard.html`, etc.) left as-is unless linked from interview chrome
- Mobbin optional (auth unavailable this pass) — principles applied from brief
- Superdesign optional — shipped as real frontend CSS/HTML/JS

## View

Server: `http://127.0.0.1:8000/` (static via FastAPI)
Flow: Landing → Login → `/dashboard` → `/challenges` → brief → `/session/:id` → report
