# Top twenty release checkpoint

October 8, 2026. Publishes the reviewed [twenty-question selection](interview-top20-manifest.json), with five additional exercises retained. The [refinement report](interview-top20-refinement.md) documents the four-part briefs, pressure cases and optional discussion boundaries. The NeetCode findings remain research; they do not silently replace this selection.

## Release changes

- Twenty ordered core questions appear in the website catalogue and their briefs. All original questions remain available.
- Every featured exercise has three baseline parts with independent case coverage and one optional, ungraded changed-requirement discussion.
- The library has 215 named public test definitions and 202 independent behavioral probes across 25 exercises. Tests use deliberate boundary, ordering, mutation, retry and state-history observations. Independent expectations remain server-owned.
- Reviewed repairs and selected wrong-repair controls are test fixtures; intentional candidate starter defects remain intact. Publication rejects missing part coverage and grading assigned to an optional discussion.
- Browser checks cover the ranked catalogue and parts, plus rendered canvas drag/history/loading and search-response races. They distinguish actual starter regressions from reviewed repairs in Chromium, Firefox and WebKit.
- Existing grading review/calibration fixtures now use the deployed registry version. The saved-editor-revision test selects a declared entry file instead of assuming every question uses `src/`. CI import checks pass.

## Verification

- Full CI-equivalent backend suite: **1,060 passed**, 180 conditional tests skipped; **77.81% coverage** versus the required 60%.
- Docker release suite run separately with isolation enabled: **154 passed**, no skips. Covers starters, references, selected incorrect repairs, reviewed public suites and evaluator integrity.
- Targeted backend authoring, parts, selection and quality checks: **113 passed**.
- Frontend API/state/editor/report checks: **46 passed**.
- All six featured TypeScript projects type-check.
- Seven consolidated release gates pass. Catalogue reference benchmark preserves ranked results; nine samples give p95 **2.91 ms** against a calibrated **27.06 ms** limit on the local Linux/ARM64 runner. This is reference release evidence, not candidate timing or production capacity evidence.
- Browser release suite: **57 passed** across Chromium, Firefox and WebKit. Covers recovery, leases, dialog accessibility, feed/labels, catalogue ordering, four-part briefs, canvas and search regressions. The contrast audit waits for the dialog entrance animation to finish before measuring.
- CI now enforces the six featured TypeScript type checks alongside the browser release suite.

The ordinary backend run skips conditional Docker/live-service tests; the separate isolated suite above is the execution evidence for question release QA. Newly added duration/difficulty labels remain provisional pending candidate calibration. Automated behavioral passes do not certify candidate understanding. Existing human-review requirements remain declared.

## Publication

The repository's `main` push triggers Backend CI. Deployment depends on backend, schema, Docker, browser and startup integration checks. A Git push alone is not evidence that the live website has updated: check that exact commit's workflow and deployment outcome. No database migration is introduced by this release.
