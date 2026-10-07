# Final performance checkpoint

Performance source changes and release repairs are merged in [PR #22](https://github.com/shrutwik/PromptCode/pull/22).
The deployed runtime matches merge `ff17f8690fd53ca6e271702760f16f1ba2a731f8`
and reviewed source `50e66e2a679d5e59d43a9182f88c40c9df47e16a`.
The frontend is live at https://promptcode-seven.vercel.app/; the existing
Modal app was deployed with tag `performance-50e66e2`.

## Release verification

- [Merged release CI](https://github.com/shrutwik/PromptCode/actions/runs/37566839108): success.
- Backend tests: 950 passed, 70 opt-in checks skipped; passing Linux coverage 77.61%.
- Repository lint, strict types for 29 configured files, locked dependency audit,
  PostgreSQL schema check, Docker builds and strict evaluator gates pass.
- Disposable startup rehearsal passes API readiness, both worker health checks,
  and repeated seed idempotency. Frontend session-state tests: 25 passed.
- Vercel reports the production deployment successful; live HTML serves workspace
  asset `20261006e`. Frontend and Modal `/ready` both return HTTP 200.
- The separate self-hosted workflow pushed images but skipped deployment because
  its SSH host was unreachable. The live Vercel/Modal deployment was verified separately.

Repair references and changed areas: [release checkpoint](performance-release-checkpoint.md).
Earlier code-level benchmarks: [first pass](performance-first-pass.md) and
[execution pass](performance-execution-pass.md).

## Authenticated workspace loading

One explicitly labeled test account and an unchanged Python practice workspace
were used. No candidate file was edited, no AI request was made, and no assessment
was submitted. Browser tests used a 1440×900 desktop viewport and disabled HTTP
cache. Each attempt released the editor lease before the next navigation; the
workspace was paused after testing.

The metric below is the page's `sessionReady` marker, after metadata/README loading
and rendering, before editor ownership/timer resume completes. It is not a full
interactive-readiness or concurrent-user capacity metric.

| Sample | Ready marker samples (seconds) | Median |
|---|---|---|
| Original production revision | 1.645, 1.047, 0.994 | 1.047 s |
| First three loads after deployment | 3.092, 1.554, 2.297 | 2.297 s |
| Repeat on deployed revision | 1.499, 1.677, 3.748 | 1.677 s |
| Original script against deployed backend | 9.273, 9.189, 7.680 | 9.189 s |
| Updated script against the same backend | 9.427, 9.312, 4.046 | 9.312 s |

The final comparison alternated scripts in one test browser by locally overriding
only the workspace JavaScript response. The server and deployed product were not
modified for that comparison. All samples above are retained, including slower
ones. These small, variable samples do **not** establish a reliable overall speedup;
initial post-deployment loads were slower than the original baseline.

The request-flow change is verified: metadata starts concurrently and README is
fetched once. Completed startup data requests fell from five to four; timer
requests are excluded from that count. Backend and hosting latency remain large
and variable enough to dominate the observed page load. Cold starts, database
round trips, workspace hydration and request scheduling need separate traces
before attributing the variance or changing limits.

Raw sanitized measurements: [performance-measurements](performance-measurements/).
The separate sequential API client samples are preserved there; they must not be
substituted for browser load time or treated as production percentiles.

## Real execution smoke test

One registered `run_tests` command ran against the unchanged starter workspace:
HTTP 200, no infrastructure error, no timeout, three tests passed and one failed.
The starter's failing test is preserved; this was execution verification, not a
candidate correctness or grading check. The workspace was paused afterward.

| Sandbox phase | Observed time |
|---|---|
| Create | 0.757 s |
| Upload source | 4.205 s |
| Execute | 1.730 s |
| Cleanup | 0.126 s |

The API reported 6.825 s execution duration; end-to-end request duration was
9.393 s. Numeric `sandbox.complete` telemetry was confirmed for this request.
Source upload consumed roughly **62%** of the measured sandbox lifecycle. In this
single sample, upload exceeded sandbox creation by more than five times.

## Highest-value follow-ups

1. Replace per-file sandbox transfer with a bounded bulk transfer while preserving
   source validation, dependency exclusions, timeout handling and cleanup. The
   measured upload cost is the clearest execution bottleneck; increasing sandbox
   count alone does not remove it.
2. Trace authenticated API connection acquisition, database calls, object storage
   hydration and container startup/placement. Page loading is still variable, and
   no production user-count or throughput claim is supported by these samples.
3. Correct the existing Monaco icon-font policy: the browser blocks its jsDelivr
   font under `vercel.json`'s current `font-src`. This was observed before and after
   deployment and was left outside the performance/release batch.

Execution capacity and timeouts remain unchanged. The task ends at this measured
checkpoint; outstanding optimizations above are documented rather than silently
claimed complete.
