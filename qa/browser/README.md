# Browser release checks

From the repository root:

```sh
sh scripts/prebuild-interview-node-deps.sh
npm ci --ignore-scripts --prefix qa/browser
cd qa/browser
npx playwright install --with-deps chromium firefox webkit
npm test
```

The loopback server serves the real frontend and the same Monaco 0.52.2 assets
used by the app, with a deterministic API fixture. No live account, AI key,
database or deployment is required. Question bundles use the actual starter
sources and the existing reviewed reference repairs in temporary directories;
the starters remain intentionally buggy. All fixture files are removed on exit.

Coverage: save-before-run and revisions, reload draft recovery, offline/reconnect,
lease conflicts, capacity retries, failed-run status, completed-attempt controls,
white Terminal text, dialog focus/Escape and WCAG AA dialog contrast. Both React
questions are rendered in real browsers, including starter regression detection
and reference label persistence through a mocked API. Chromium, Firefox and
WebKit run the same assertions without retries. Failures retain traces and
screenshots; the report is in `report/`, artifacts in `results/`.

These are frontend integration checks. The separate Docker release checks cover
real question APIs, reviewed practice suites, signed independent evaluation and
grading attacks. Browser fixtures do not establish live authentication, network
capacity, candidate-grade validity or accessibility of every app page. They never
run arbitrary candidate submissions on the host and are never grading evidence.

The CI browser job and isolated runner job must pass before the deployment job
can run. Browser reports, isolated test results and calibrated reference timing
are retained as release artifacts for seven days.
