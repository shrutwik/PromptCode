# Product quality plan and execution checkpoint

Reviewed 2026-10-07. Scope: assessment integrity, coding-question quality,
candidate workspace reliability, and release enforcement for the existing app.

## Published references

| Source | Published design | Application here |
| --- | --- | --- |
| [HackerRank test-case design](https://support.hackerrank.com/articles/8626818013-defining-test-cases-for-coding-questions) | Sample/hidden cases, corner cases, weighted scoring and debug feedback | Keep practice output advisory; validate weighted server-owned cases independently, including incorrect repairs |
| [HackerRank project assessments](https://support.hackerrank.com/articles/1626384486-hidden-test-cases-for-front-end,-back-end-and-full-stack-questions) | Validate project test declarations before publishing; keep hidden files out of candidate workspaces | Add a coding-question publish gate and require isolated reference/attack checks before deployment |
| [CoderPad multi-file frameworks](https://coderpad.io/resources/docs/interview/quick-start-guides/multi-file-frameworks-for-engineers/) | Browser IDE, rendered UI, API exercises and realistic projects | Exercise real Monaco and candidate workflows in a browser; test React question behavior in Chromium, Firefox and WebKit |
| [CodeSignal assessments](https://support.codesignal.com/hc/en-us/articles/22112130416535-Quick-Start-Guide-Assessments) | Consistent expert-maintained assessments, verification and research-backed evaluation | Preserve evidence review and real-pilot calibration gates; do not equate passing automated tests with validated hiring scores |

These are public product/architecture descriptions, not access to competitors'
private systems or independent proof of their claims. No proprietary implementation
is copied. The existing FastAPI, frozen snapshots, isolated executors, signed
results, leased workers and human evidence review remain the architecture.

## Execution plan

1. **Release enforcement:** extend the existing Docker CI job to execute independent
   grading inventories, starter regressions, reviewed visible suites, plausible
   incorrect repairs, signing/replay and runner attacks. A skipped local opt-in
   suite must not count as a release pass. References: `test_trusted_evaluator.py`,
   `trusted_reference_fixtures.py`, and the current backend CI workflow.
2. **Browser verification:** add pinned browser-test tooling and offline fixtures
   using the real editor/assets. Cover saving before execution, draft recovery,
   offline/reconnect, capacity retries, terminal styling and dialog keyboard
   behavior; exercise both React questions in Chromium, Firefox and WebKit. Keep mocked browser API
   checks distinct from backend integration and live deployment evidence.
3. **Performance verification:** replace one-shot latency assertions with warmed,
   repeated measurements and add deterministic work-growth checks. Record a
   reviewed reference measurement with environment and distribution data for
   release QA. Keep candidate-reported timing/scans advisory.
4. **Question publication:** add a requirement-to-case contract and release gate
   covering all ten questions, visible test floors, independent inventories,
   commands, immutable controls, and declared coverage gaps. Document the
   architecture and verification results with reproducible commands.

Each item is verified before expanding scope. Production deployment and external
account/data changes are outside this local implementation pass.

## Launch evidence that engineering cannot fabricate

Real pilot attempts, paired qualified reviewers, assessment calibration and an
independent deployment/security audit still require real external evidence. The
existing score-publication controls stay closed until those requirements pass.
Capacity results must come from the intended deployment and workload; local
browser tests or reference microbenchmarks cannot establish production capacity.
See `grading-operations.md`, `capacity-validation.md`, and `release-checklist.md`.

## Verification checkpoint

Completed locally:

| Item | Change and files | Verification |
| --- | --- | --- |
| Release enforcement | `.github/workflows/backend-ci.yml`, Node runner/backend images, `test_interview_question_release.py`, trusted inventories and evaluator regressions | 105 isolated Docker checks passed, none skipped; all ten reviewed practice suites passed (67 visible cases), 62 independent cases and 20 incorrect repairs exercised; actual Node 24.20.0 image built |
| Browser reliability | `qa/browser/`, `interview-session.js`, `interview.css`, versioned HTML assets | 39 checks passed across Chromium, Firefox and WebKit: real Monaco, both React questions, white Terminal, draft recovery, failure status and dialog accessibility; lifecycle pause now survives navigation; 38 frontend helper checks passed |
| Performance | Catalog practice suite, `run_interview_performance_gate.py`, regression tests | Isolated reviewed reference: p50 10.169 ms, p95 36.640 ms against calibrated 85.786 ms limit; correct ranking verified; repeated samples, warmup and runtime/image provenance recorded |
| Question publication | `interview_quality_contract.json`, `run_interview_publish_gate.py`, registry metadata and gate regressions | All ten requirement mappings validate; fixed stale entry-file pointers in four questions; all seven strict release gates passed |

Backend verification: the final full hermetic run outside local socket
restrictions passed 979 tests and skipped 90 explicit Docker/opt-in checks, with
no failures. The separate isolated Docker run passed all 105 selected release
checks without skips. Publication regression checks, backend lint, strict
type checks (29 files), and frontend helper checks also passed. QA dependencies
reported zero known vulnerabilities at install time.

Evidence: `output/quality/2026-10-07/interview.xml` and
`output/quality/2026-10-07/reference-performance.json`, and
`output/quality/2026-10-07/backend-final.xml`. Browser reports and traces
are reproducible through `qa/browser/README.md`. Local benchmark measurements
are environment-specific, not production capacity or candidate scoring evidence.
CI now requires isolated checks and the browser job before deployment and retains
quality artifacts for seven days; remote CI and deployment were not run here.

Reproduce the static gates with `cd backend && python -m
scripts.run_release_quality_gates --strict`; run isolated checks using the exact
four-file command and environment in the CI workflow. The existing independent
review, live capacity, security audit and pilot calibration work remains required
before making production-readiness or hiring-validity claims.
