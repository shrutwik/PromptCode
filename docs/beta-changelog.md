# Beta changelog

## 2026-10-08 — Featured question progression

- Give each featured question three explicit baseline parts and an optional changed-requirement discussion; show them in the interview brief.
- Add twenty visible pressure fixtures and twenty independent probes; 215 visible definitions and 202 probes in the retained 25-question library.
- Publication checks enforce part coverage and exclude discussion from grading. Registry version 4; evaluator v5.
- [Reviewable refinement report](interview-top20-refinement.md). Changes remain local before push.

## 2026-10-07 — Ranked top twenty completed

- Added the five missing overall-ranked families: canvas editor, hand comparison, runway simulation, search/routes and durable wallet transfers.
- Feature the exact reviewed top twenty; retain five additional exercises. Candidate library cards show core rank.
- Registry version 3; evaluator v4; 182 independent probes across 25 exercises.
- [Selection and implementation checkpoint](interview-top20-implementation.md); production deployment and calibration remain separate release work.

## 2026-10-07 — Interview library expansion

- Local interview registry expanded from ten to twenty questions, version 2.
- Existing prompts and reviewer notes now expose invariants and verification checkpoints; ten added regression checks preserve candidate starter incidents.
- Ten original runnable Python exercises, eighty visible tests and eighty independent probes; behavioral evaluator version `behavioral-2026-10-v3`.
- Isolated runner QA: 129 passed; authoring QA: 40 passed; related inventory/task tests: 32 passed.
- Source coverage, access limits and pending calibration: [implementation report](interview-library-expansion.md). Production deployment remains a separate release step.

## 2026-09-18 — Private beta ops

- Invite codes + optional email allowlist (`PROMPTCODE_BETA_INVITE_REQUIRED`)
- User cohort fields: `beta_cohort`, `signup_source`, `invite_code_id`
- Product analytics events + funnel / challenge quality aggregates (internal)
- Calibration overview, session review, human review (separate from automated score)
- Feedback fields: AI expected, confusing/broken, most-like-real-interview
- Optional abandon reason; infra failure tags; wall/active/infra-blocked durations
- Persist `scoring_version=v1` and `challenge_version` on sessions/evaluations
- Internal user list/disable/enable; anonymized calibration export
- Docs: release checklist, ops alert thresholds, challenge revision workflow

Score changes are **explicit / reviewed / versioned** only — no auto-recalibrate from recent users.
