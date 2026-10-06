# Grading operator workflow

Implemented: frozen submissions, durable leased jobs, independent behavioral
inventories for all ten questions, signed results, staff reviews, owner appeals,
optional bounded DeepSeek evidence feedback, and real-pilot calibration tools.
These are practice assessments. Real pilot calibration and independent deployment
audits have not been performed. Publication is off by default.

## Prepare the server

1. Deploy the changed backend/executor/worker image, rebuild both interview runner
   images, and apply `alembic upgrade head` including `audit03_interview_grading`.
2. Set `PROMPTCODE_GRADING_SIGNING_KEY` to a separate random secret of at least 32
   bytes in the backend, executor and workers. A local key was generated in ignored
   `.env`; it was not printed or committed. Keep it away from candidate containers.
3. Keep backend and executor on the same configured submitted-source storage path.
   Preserve `.submitted/` and its database jobs across restarts. Retain source while
   reviews/appeals/history need it; choose and document a deletion policy before
   expanding beyond the limited beta. Files are read-only to candidate containers;
   digest verification detects host edits. Application/host administrators remain trusted.
4. Start both persistent queue workers. Jobs are claimed atomically, expire their
   leases after the bounded execution window, and retry infrastructure failures up
   to three times. Failed jobs have no grade. An old lease cannot finish a new attempt.
   Each account can have at most three queued/running grading jobs. Admission is
   checked before freezing another submission and also applies to staff retries;
   PostgreSQL serializes simultaneous requests for the same account.
5. Set `PROMPTCODE_GRADING_FEEDBACK_ENABLED=true` only if optional paid staff feedback
   is wanted. Its single-call suggestions use the same trial/day/user/session caps
   and kill switch; they do not assign ratings. Default is false.

Production must pass the independent execution-host audit: the default Compose
executor still holds Docker daemon authority and application credentials. Container
isolation tests are not proof against host/kernel escape or executor compromise.
Use dedicated execution infrastructure with restricted privileges before enabling
published grades. The narrow authenticated job endpoint is implemented; a separate
privilege-limited host/broker deployment is still an operational/security prerequisite.

## Candidate and staff flow

Candidates use the normal question workspace, run advisory tests and submit. Submission
freezes source and queues external evaluation, returning immediately with pending status.
Further edits are blocked. Retrying submit returns the same report/job. Post-submit defense
answers revise the evidence packet and invalidate a previous review of that packet.

Create staff accounts normally, then grant the reviewer role from a trusted server shell:

```sh
PYTHONPATH=backend .venv/bin/python -m scripts.manage_grading_reviewer reviewer@example.com --grant
```

Revoke with `--revoke`. This command changes an existing account only and audits the role
change. It is not exposed through signup or a public API. Do not grant this role to
ordinary candidates: reviewers can inspect other candidates' assessment evidence.

After evaluation completes and the candidate finishes defense, open
`/grading?session=<session UUID>` while signed in as a reviewer. Inspect the frozen
source, event evidence, transcript, defense answers and verified external result.
Enter every applicable 0–4 dimension rating with evidence IDs and rationale. Explicit
manual checks are required for uncovered rendering, performance and structural
requirements. Functional failures cannot receive a meets/strong correctness rating.
Self-review is prohibited. Saved revisions remain staff-only until publication gates pass.

Candidate published reports include an appeal form. Appeals are scoped to the owning
account/current review and require an independent reviewer to adjudicate. Pending or
re-review-required appeals withhold the current rating. Re-review appends a revision
instead of replacing history. The staff page lists appeals and records a reasoned decision.

## Calibrate with real attempts

Run a real pilot with at least 30 attempts for each of the ten questions. Obtain two
independent, blinded qualified human reviews of each same source/evidence revision.
Cover correct, partial, wrong, polished-but-wrong, no-AI, interrupted and adversarial
attempts. Preserve the reviewer workflow/audit evidence; distinct account IDs alone do
not demonstrate independence. Do not label test fixtures as real pilot attempts.

Export matched persisted reviews from the trusted server:

```sh
PYTHONPATH=backend .venv/bin/python -m scripts.export_grading_calibration --confirm-real-pilot --output /private/tmp/grading-pilot.json
PYTHONPATH=backend .venv/bin/python -m app.services.interview.grading_calibration /private/tmp/grading-pilot.json --audit-evidence /path/to/operator-audits.json --output /path/to/protected/grading-readiness.json
```

`--confirm-real-pilot` is an operator attestation, not automatic empirical verification.
The exporter verifies signed results, frozen bytes, source/packet/version bindings and
two distinct complete reviewers. It excludes stale/invalid records and omits candidate
source, transcripts and contact information. Protect pilot/reviewer records as sensitive
assessment data. Audit evidence must include the independent checks documented in
`grading-research-and-architecture.md`; missing evidence leaves readiness false.

Only after the actual pilot and audits pass, configure the protected readiness report
path and enable `PROMPTCODE_GRADING_PUBLISH_REVIEWED_SCORES=true`. The application
recomputes readiness rather than trusting a boolean, and rejects stale challenge,
evaluator or inventory versions. Offline reports include agreement confidence intervals;
online checks avoid repeated bootstrap calculations. Keep the readiness file outside
candidate-writable storage. Scores remain human-reviewed practice ratings, not validated
hiring decisions, percentiles or guarantees of correctness on every possible input.

## Failure recovery

Missing signing configuration, unavailable executors, Docker communication failures and
timeouts leave the review pending or job failed. Capacity limits do not become incorrect
grades. Fix infrastructure first. After exhausting automatic retries, an authorized staff
operator can retry the failed job through `POST /api/interview/grading/sessions/<id>/retry`;
this resets the bounded retry allowance, verifies frozen source and records an event.
Never alter stored results/signatures/leases to manufacture completion. Version changes
require a new attempt, not relabelling an old source as a newer challenge.
