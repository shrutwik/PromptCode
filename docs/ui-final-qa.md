# PromptCode UI — Final QA Notes

Pre-beta QA pass (2026-09-18). Validation + surgical fixes only. No Superdesign / redesign.

## Verdict
**GO for private beta** — core authenticated E2E exercised (API + Chrome headless/CDP). See `docs/pre-beta-checklist.md`.

## Brand / color
- [x] Chartreuse `#c8f060` as `--pc-accent` in `pc-tokens.css`
- [x] Landing / login / signup accents aligned
- [x] `--pc-ai` cool blue for AI / provenance (≠ success green `#3ecf8e` / landing `#60d4a8`)
- [x] Semantic success / warn / danger unchanged roles
- [x] Contrast: chartreuse-on-near-black CTAs verified in screenshots (large text/buttons OK)
- [x] Legacy leaderboard / challenges / playground already on graphite+chartreuse (no brand-blue leftovers; AI blue preserved)

## Timeline (report)
- [x] Categories: Exploration, AI, Coding, Testing, Recovery, Submission
- [x] Horizontal scrubber: proportional time, marks, drag, keyboard (`role=slider`), linear playhead
- [x] Compact list + detail pane; AI payloads behind `<details>`
- [x] Recovery sequences only when AI accept → fail → revert → pass present
- [x] Phase mini-map
- [x] Live browser scrub with real submitted session (`/session/{id}/report`) — End/Arrow keyboard advances playhead

## Report hierarchy
- [x] Score hero (score, title, duration, status, tests) — no Meta-ready / percentile claims
- [x] Order: overall → what happened → categories → strengths → improvements → recovery → timeline → diff → defend → feedback
- [x] Rubric max totals **100**: A25 + B15 + C15 + D15 + E10 + F10 + G10 (not `15*4+25+10+5`; still sums to 100)
- [x] Diff → timeline file link when `payload.path` exists

## Workspace / library / dashboard
- [x] Authenticated dashboard / library / challenge detail / workspace / report screenshots (1440×900)
- [x] Public landing/login/signup also 1366 / 1920 / 390 / 768
- [x] Workspace timer timezone fix (naive UTC ISO no longer shows negative elapsed)
- [x] Palette groups + offline indicator unchanged

## Motion
- [x] Reduced-motion emulated (`prefers-reduced-motion: reduce`) — landing still loads
- [x] No new landing effects added this pass

## A11y
- [x] Focus-visible chartreuse ring in tokens
- [x] Scrubber keyboard verified via DOM `KeyboardEvent`
- [ ] Full keyboard smoke of submit modal + defend answers (partial — defend UI present; not fully walked)

## Analytics / regression
- [x] Event type strings not renamed
- [x] `final_diff_viewed` **only** via `GET /diff?record=true` (Review Changes) — removed from client POST allowlist
- [x] Smoke: signup×2 → start → edit → tests → AI → diff(record) → submit → report → feedback
- [x] Isolation: cross-user session GET **404**; dashboard does not leak peer sessions
- [x] Double-submit returns 200 (idempotent path)
- [x] No secret material in report JSON (`sk-` / JWT / API keys)

## Runtime this pass
| Item | Result |
|------|--------|
| Migrations | `alembic upgrade head` OK (sqlite `./dev.db`) |
| `verify_interview_mvp.py` | OK |
| Interview tests | 27 passed, 1 skipped |
| Full `backend/tests` | 314 passed, **5 failed** (legacy SDK guide / sandbox-token / prompt-judge / release gates — not interview MVP) |
| `beta_smoke.py` | OK |
| Runner | **local** (`/health/ready`) — Docker images **not** built; Docker E2E **not** run |
| AI | **mock** (`mock-interview-v1`) despite key present — `PROMPTCODE_AI_PROVIDER` defaults to mock |
| Browser MCP | unavailable; Chrome headless + CDP used |

## Fixes this pass
1. Workspace elapsed timer: parse naive API timestamps as UTC; clamp negative display (`interview-session.html`)
2. Report `parseTs`: same UTC normalization for scrubber timing (`interview-report.html`)
3. Disallow POST of `final_diff_viewed` via `/events` — only Review `diff?record=true` (`interview.py`)

## Visually inspected vs not
**Inspected (screenshots under `.qa-screenshots/`):** landing, login, signup, leaderboard, playground redirect, auth dashboard/library/detail/workspace/report, mobile landing, reduced-motion landing.

**Not fully walked in UI:** defend answer submit, concurrent multi-tab edit races, Docker runner path, production OpenAI path.
