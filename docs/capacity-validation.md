# Capacity rehearsal for 50–100 users

The product is not hosted yet. A local rehearsal measures the current implementation and catches integration failures; it cannot establish capacity on a future production machine. Run this again against the final isolated deployment before opening the beta.

## Reproduce locally

From the repository root, with the existing Python virtual environment and Docker available:

```sh
.venv/bin/python backend/benchmarks/run_local_capacity.py \
  --output docs/capacity-local-results.json --stages 50 100
```

The runner creates its own randomly named PostgreSQL 16.11 container with ephemeral storage, applies the actual migrations, provisions 100 disposable benchmark accounts, and starts one backend, one credential-free execution broker and two durable workers. The broker uses the prebuilt `promptcode-runner-python:latest` and `promptcode-runner-node:latest` images. Build those images first if they are absent. All processes and the database container are removed afterwards. Existing databases, volumes and users are untouched. Paid AI is disabled and no assistant or legacy provider endpoint is called. Temporary access tokens have mode `0600` and are removed with the temporary directory.

Each simultaneous user verifies their authenticated identity, reads a challenge, creates their own session, reads and edits a source file, runs real advisory Docker tests, submits an immutable snapshot, reads and answers a defend question, polls the report until durable trusted grading completes, and reads their dashboard. The starter remains intentionally buggy: candidate test failures are valid execution results, while unavailable runners, grading failures and missing reports fail the flow. Registration, password hashing and paid AI throughput are outside this workload.

The default stages launch 50 users, wait for completion, then launch 100 users. Each user owns a separate account and session; the same benchmark accounts may create a new session in the second stage. At most 100 client threads exist. A stage has a 600-second deadline, request timeouts are bounded, and advisory overload has at most ten retries with jitter. The test stops scheduling further stages if unexpected HTTP errors exceed 10% or explicit throttles exceed 25% after at least 20 requests. Any incomplete user flow makes `workflow_completed` false and exits unsuccessfully. `capacity_validated` remains false: completion and readiness are separate conclusions. Intentional overload is reported separately from unexpected failures. Per-stage readiness gates report unexpected errors and whether the advisory shed fraction exceeds 25%; latency acceptance and production headroom remain explicitly unassessed. Adjust bounds through the authenticated workload's CLI only after understanding the measurements.

Reports include per-operation HTTP status counts and p50/p95/p99 latency for all requests and successful responses separately, explicit throttle counts, completed/incomplete flows, real advisory execution duration, durable job statuses, retry attempts, queue waiting and execution duration. Durable timing uses the latest worker claim for each job; when retries occur, queue waiting includes retry backoff. Client-observed queue waiting is an upper bound based on polling and may miss very fast jobs. The local runner additionally measures host load, host process CPU, selected service RSS, memory and disk space once per second, and records Docker's available CPU and memory. Host process CPU is the sum reported by `ps`, not an instantaneous kernel utilization counter. Selected service RSS excludes the PostgreSQL and runner containers inside Docker's VM. Local Docker allocation and shared developer-host activity differ from a production server.

If a protective throttle stop prevents measuring completion under intentional overload, retain that report and run a separate diagnostic rehearsal with explicitly relaxed protection:

```sh
.venv/bin/python backend/benchmarks/run_local_capacity.py \
  --output docs/capacity-local-diagnostic.json --stages 50 100 \
  --max-throttle-rate 0.5 --capacity-retries 20
```

This keeps four broker execution slots and two workers. It allows additional bounded retry traffic so queue draining can be measured. It does not relax the 10% unexpected-error stop criterion or the separate 25% advisory-shedding readiness gate. The benchmark performs these retries automatically; browser retry behavior and perceived user experience are outside this measurement. Completion with many retries is not evidence of acceptable interactive latency. The chosen bounds are embedded in the report.

For a quick database/API measurement without candidate execution:

```sh
.venv/bin/python backend/benchmarks/run_local_capacity.py \
  --output docs/capacity-local-api-results.json --stages 50 100 --skip-execution
```

That mode exercises real authenticated APIs, sessions, file persistence, submission queue admission, defend and report retrieval. Jobs remain queued; it does **not** verify execution or worker throughput. The report explicitly marks that scope.

## Run on the future deployment

Use a staging environment with the production topology and resource budget, fresh disposable accounts, paid AI disabled, and monitoring enabled. Provision account tokens ahead of the run; account creation is deliberately excluded from simultaneous work. Keep this account file private:

```json
{
  "namespace": "staging_pilot",
  "disposable": true,
  "accounts": [
    {
      "email": "benchmark_staging_pilot_0@example.com",
      "access_token": "TOKEN_FROM_DEDICATED_BENCHMARK_ACCOUNT"
    }
  ]
}
```

Provide 100 distinct accounts matching `benchmark_<namespace>_<number>@example.com`. The workload checks the email returned by `/api/auth/me` before any session mutation, so a mislabelled real-user token cannot be used. It never creates or deletes accounts. Access tokens currently expire after 15 minutes; prepare them immediately before the run. Keep the account file outside the repository, restrict its permissions, and never commit it. The report contains no tokens, passwords, response bodies or source contents. Redirects are disabled for credentialed requests. Remote targets require HTTPS.

```sh
cd backend
../.venv/bin/python -m benchmarks.interview_load \
  --base-url https://YOUR-STAGING-HOST \
  --accounts /private/path/benchmark-accounts.json \
  --namespace staging_pilot --stages 50 100 \
  --output /private/path/capacity-results.json
```

Collect host, database, queue and isolated execution-host monitoring in parallel. Do not use `--local-host-telemetry` against a remote URL: the load generator's resources are not the server's. The remote report includes client-observed queue timing; use server job/queue monitoring for authoritative worker timing and memory/disk limits. Retain partially completed sessions for diagnosis and let the normal retention policy clean up benchmark artifacts. Do not delete real accounts or data.

Review both stages, all flow failures and intentional throttles, p95/p99 response time, queue wait, grading completion and resource headroom. A completed local workflow establishes local behavior under this workload only. Choose the beta's acceptable response and grading delays explicitly, then apply those same bounds to the deployed test. A small cohort with staggered requests has different requirements from 100 users running tests at once.

## Measured local checkpoint (2026-10-05)

[Measured report](capacity-local-results.json) records a macOS developer computer sharing the backend, broker, load client and two workers. Docker had 11 CPUs and 8.22 GB available; the broker retained four execution slots. No paid AI ran. The diagnostic measurement allowed a 50% protective throttle threshold and twenty advisory retries; the separate advisory-shedding readiness gate remained 25%.

| Stage | Completed workflows | Total stage duration | Unexpected HTTP failures | Advisory shed responses | Grading queue p95 | Session creation p95 |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 50 users | 50/50 | 63.06 s | 0 | 204 | 20.56 s | 10.51 s |
| 100 users | 100/100 | 132.13 s | 0 | 527 | 52.67 s | 28.78 s |

All 150 admitted grading jobs completed with zero durable retries and no unexpected HTTP errors. This establishes completed local workflows under bounded automatic retries, not acceptable interactive capacity. Advisory requests were shed on 80.3% of attempts at 50 users and 84.1% at 100 users: both exceed the separate 25% readiness gate. At 100 users, source-save p95 was 7.43 seconds and session creation p95 was 28.78 seconds; grading queue p95 was 52.67 seconds. Production capacity and latency acceptance remain unverified.

The [earlier diagnostic report](capacity-local-before-pool-fix.json) completed 98/100 workflows; two source saves returned 500 after the database pool's five-second wait expired during storage admission. The final implementation moves filesystem work off the API event loop and releases the database connection before workspace creation, then gives the same 20 pooled connections plus 10 overflow connections a bounded 15-second wait. Save and submission row locks and storage quotas remain atomic. The longer wait eliminated the measured pool failures in the final run; it does not remove full filesystem scans or their scaling cost.

The [initial before-fix report](capacity-local-before.json) preserves the 50-user failure that exposed blocking filesystem work in the API. The [protective-stop report](capacity-local-throttle-stop.json) preserves the first run after that fix: it had zero unexpected HTTP errors, but the conservative throttle stop interrupted the workload. The diagnostic runs allowed overload to continue so worker completion and the remaining pool failure could be observed and fixed. Changing the diagnostic protection is not a readiness pass.

Local telemetry recorded selected native service RSS peaking at 382.4 MB, at least 20.54 GB host disk free, and host process CPU sum peaking at 1015.6%. The CPU total includes the developer computer's other processes and can exceed 100% across cores. These readings exclude per-container RSS inside the Docker VM and therefore do not establish a complete production memory budget. The retained JSON includes the full sampled series and the precise telemetry scope.
