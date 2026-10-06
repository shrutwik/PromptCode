# Interview grading v3: evidence before scores

Research reviewed: 2026-10-05. This is a representative review of primary research
and published assessment-provider guidance, not an exhaustive census of the web.
Provider product claims are not independent validation. The proposed weights and
release criteria below are product decisions, not numbers established by papers.

## What exists today

`services/interview/rubric.py` has legacy activity heuristics: file views, test runs,
suggestion acceptance/rejection, reverts and communication keywords. These do not
establish competence. `execution_feedback.py` deliberately suppresses their grades.
Candidate code and the reporter currently share an interpreter, so even a complete
passing report cannot authenticate correctness. The legacy submission evaluator
(`services/evaluation/scorer.py`) is a different assessment of prompt-based tasks;
its fuzzy accuracy and prompt-quality scores must not become repository interview
grades. Historical attempts remain advisory and are not retroactively regraded.

## Research and implications

| Primary source | Finding / scope | Decision for PromptCode |
|---|---|---|
| [Sackett et al., selection-system validity, 2023, peer-reviewed](https://www.cambridge.org/core/journals/industrial-and-organizational-psychology/article/revisiting-the-design-of-selection-systems-in-light-of-new-findings-regarding-the-validity-of-widely-used-predictors/A20984B138319E3D432E643978BF026D) | Job-specific structured interviews and work samples are among stronger predictors; validity varies by setting. | Use task-specific behavioral anchors, consistent follow-ups and local validation; no claim that our score predicts job performance. |
| [Forsgren et al., SPACE, 2021, ACM Queue](https://www.microsoft.com/en-us/research/publication/the-space-of-developer-productivity-theres-more-to-it-than-you-think/) | Developer productivity has several dimensions; activity alone is insufficient. | Do not score click counts, lines changed, prompt volume or speed as competence. |
| [Becker et al., METR, 2025, preprint/RCT](https://arxiv.org/html/2507.09089v2) | Experienced developers on familiar repositories took longer with the early-2025 tools studied, despite expecting gains. | Measure infrastructure-adjusted time for operations only; do not equate faster AI use with stronger engineering. This result does not generalize to every tool/task. |
| [Shen and Tamkin, AI and coding-skill formation, 2026, research/preprint](https://www.anthropic.com/research/AI-assistance-coding-skills) | Learning an unfamiliar library with AI could impair subsequent understanding; interaction strategy mattered. | Assess code reading, debugging and transfer through post-task defense, separate from final output. |
| [Perry et al., security with AI assistants, CCS 2023](https://arxiv.org/abs/2211.03622) | In the studied security tasks, AI-assisted participants produced less secure code and were more confident. | Include task-relevant security/regression checks and require evidence for confidence. |
| [Sandoval et al., Lost at C, USENIX Security 2023](https://arxiv.org/abs/2208.09727) | Another task/model setting found a smaller security effect. | Do not impose a blanket penalty for AI use; assess the actual artifact and review. |
| [Zheng et al., MT-Bench / Chatbot Arena, NeurIPS 2023](https://arxiv.org/html/2306.05685v4) | LLM judging can show ordering, verbosity and self-preference biases. | A model can suggest evidence, not authenticate tests or issue final ratings. |
| [Chen et al., judgment biases, EMNLP 2024](https://arxiv.org/abs/2402.10669) | Both human and model judges can be affected by irrelevant perturbations. | Blind irrelevant identity information, calibrate reviewers and support audit/appeal. |
| [Karat human + AI rubric, provider guidance](https://karat.com/resource/human-ai-technical-interview-rubrics/) | Separates completion, navigation, implementation quality and judgment; evaluates oversight of AI. | Separate outcome from process and require observable evidence. |
| [HackerRank AI-assisted interviews, provider documentation](https://support.hackerrank.com/articles/5821380141) | Interviewers can inspect transcripts, planning and diffs and ask follow-ups. | Preserve a reviewable evidence trail; assistance mode must be recorded. |
| [CodeSignal AI-assisted assessments, provider announcement](https://codesignal.com/blog/introducing-ai-assisted-coding-assessments-interviews/) | Offers differing assistance modes with transcript/session replay. | Compare only attempts with comparable challenge, rubric and assistance policy. |

These sources support the design principles; none validates this particular rubric,
DeepSeek as an interview judge, or a hiring cutoff for this application.

## Rubric and observable anchors

Each assessed dimension receives an integer rating 0–4. `null` means not assessed;
it is never treated as 0. Rating 0 requires affirmative evidence of an incorrect
approach. 1 = weak, 2 = partial, 3 = meets the task, 4 = strong, demonstrated beyond
the basic case. Every rating needs a cited evidence ID and written rationale.

| Dimension | Weight | 0 | 2 | 3 | 4 |
|---|---:|---|---|---|---|
| Functional correctness | 35 | Demonstrably violates the core requirement | Core behavior partly works; important cases fail | Core requirements and required regressions work | Task-specific boundary, negative and integration cases also work |
| Problem diagnosis | 15 | Demonstrably wrong root cause | Finds relevant symptoms, causal explanation incomplete | Explains the causal path and supports it with code/reproduction | Tests competing hypotheses and explains system boundaries |
| Implementation quality | 15 | Introduces a demonstrated serious regression | Fix works partially but adds avoidable risk | Scoped fix follows repository contracts and handles required errors | Clearly justified design, task-relevant security/performance and maintainability |
| AI oversight | 10 | Demonstrably relies on an incorrect suggestion despite contrary evidence | Some review but assumptions remain unchecked | Evaluates suggestions against requirements and verifies adopted changes | Detects a meaningful limitation and explains a stronger alternative with evidence |
| Verification | 15 | Tests demonstrably do not exercise the claim | Happy-path evidence with important coverage gaps | Relevant regression and negative checks, results interpreted correctly | Distinguishes a plausible wrong fix and tests task-specific boundary/risk cases |
| Explanation and ownership | 10 | Explanation contradicts submitted behavior | Describes edits, but rationale/risks incomplete | Explains root cause, fix, proof and limitations | Correctly predicts behavior under a new task-relevant variant |

Rating 1 is between the specific 0 and 2 anchors, not an automatic missing-data
fallback. Recovery is evidence within verification/diagnosis, not separate points:
manufacturing failures/reverts must not improve a grade. Opening a file does not
prove diagnosis; rejecting AI does not prove oversight; saying "rejected" does not
prove communication. More AI calls do not raise scores. If no successful assistant
response was available, AI oversight is not applicable; no-AI/budget-denied users
are neither rewarded nor penalized. Show the denominator and do not compare totals
across different applicable dimensions. Security-critical failures must be flagged
for reviewer attention, not silently averaged away.

For a fully reviewed practice attempt:
`total = 100 * sum(weight * rating / 4) / sum(applicable weights)`.
Do not emit a total until every applicable dimension has evidence and a human
review. No automatic pass/fail, seniority labels, percentile or hiring recommendation.
Correctness ratings need an external evaluation reference; visible stdout is not
acceptable evidence for that dimension. Other ratings are review judgments, not
claims of objectively measured mental ability.

## Architecture and trust boundaries

1. **Capture:** existing server session events, submitted diff, assistant transcript,
   execution attempts and defense answers. UI events indicate activity, not truth.
   Facts retain IDs/provenance and are scoped to the owning session and challenge.
2. **Freeze:** current v3 evidence packets bind session ID, challenge/version, rubric
   version and a digest of the observations. This detects packet/review mismatches;
   it is not a signature and does not freeze/authenticate candidate source. Production
   correctness still requires an immutable source snapshot and its SHA-256 manifest.
3. **Execute:** preserve advisory Docker practice. Authoritative execution must use
   the external evaluator described in `audit-trusted-execution-design.md`: candidate
   code never shares the evaluator interpreter, expected outputs or result credentials.
   Per-challenge HTTP/stdin adapters, weighted versioned test inventories and signed
   complete results are required. Candidate output and booleans cannot mint authority.
4. **Extract:** a future bounded DeepSeek job may suggest observations/rationale,
   quoting evidence IDs and counterevidence. All candidate text is untrusted data;
   no tools, network or privileged actions are exposed to the judge. JSON validity is
   not semantic validity. Failures/budget exhaustion yield pending review, not zero.
   This round makes no additional provider calls and does not activate model grading.
5. **Review:** the grading engine accepts internal human review records bound to the
   exact packet. It rejects unknown/missing evidence, extra dimensions, invalid ratings,
   mismatched revisions and AI-only reviews. A reviewed practice score is still advisory.
   The library does not authenticate reviewers or external evaluator evidence; its caller
   must use staff authorization and verified evaluator results. No public review-write API
   exists yet, and the engine is not connected to candidate-controlled input.
6. **Report:** current production reports show v3 assessment criteria and pending
   status, never fake zero grades. Defensive-answer updates revise the evidence packet
   and invalidate future reviews against the old digest. Historical grades stay suppressed.
7. **Audit:** future review persistence needs reviewer identity, immutable assessment
   revision, rubric/model/prompt versions, timestamps, overrides and appeal reasons.
   Idempotent jobs, DB uniqueness and transaction locks prevent duplicate/replayed results.

Production execution host must be separate from application/DB secrets. An executor
holding the Docker socket is privileged; non-root execution is not a sufficient broker.
The restricted broker and trusted adapters remain implementation work, not a security
property delivered by this rubric. Require tenant-isolation and malicious-code audits.

## Standard defense, opportunity and fairness

Use the existing four task-specific questions: root cause, proving test, rejected
alternative and remaining risk. Follow with one variant of the actual submitted code
to assess transfer. Keep answer guides server-only. Self-reported answers are evidence
to review, not proof that actions occurred. Explicitly tell users whether AI is allowed
during defense; take-home text cannot be described as unaided understanding. Language
style, confidence, verbosity, demographic attributes and camera behavior do not score.
Missing telemetry, provider failure and time spent waiting need separate infrastructure
status. Do not penalize accommodations, alternate valid code paths or justified broader
fixes merely because a file is absent from a preferred-file list.

## Release gates and validation plan

The rubric engine, frozen-source jobs, leased workers, signed external results,
behavioral inventories for all ten questions, authenticated staff reviews, appeals,
optional budgeted DeepSeek suggestions and calibration tooling are implemented.
Reviewed score publication is off by default. Real pilot calibration and independent
deployment audits have not been performed. Do not advertise the system as a validated
hiring assessment. See [operator setup and recovery](grading-operations.md).

Before publishing reviewed scores, build an anchor set covering correct, partial,
incorrect, polished-but-wrong, no-AI, interrupted and adversarial attempts for every
challenge. Two blinded qualified reviewers independently rate the same evidence and
adjudicate disagreements. Proposed pilot: at least 30 diverse attempts per challenge;
report weighted agreement/ICC with confidence intervals, per-dimension confusion,
review overrides, missingness and latency/cost. This sample is a starting point, not
proof of validity or enough data for every fairness subgroup.

Pre-register agreement targets before looking at results (initial engineering target:
weighted kappa >= .70 and <= 5% disagreements greater than one anchor; revisit with
measurement experts). Validate task inventories using known-good implementations,
plausible wrong fixes/mutants and malicious exit/report/replay attacks. Require no
forged authoritative result in the adversarial suite. Test textual prompt injection,
irrelevant verbosity, reordered evidence, retries, stale packets and source mismatches.
For any AI extraction, measure evidence-citation accuracy and human override rate;
model self-confidence is not a calibrated confidence measure. Keep model calls under
the same budget/kill switch and display pending when unavailable.

Evaluate accessibility and group differences using consented, separately protected
data. A pilot cannot establish job-performance validity; that requires a properly
designed local outcome study. Preserve practice-only mode until the above evidence
supports enabling reviewed grades. Do not silently reinterpret older attempts.

## Evidence feedback and pilot operations

`services/interview/grading_feedback.py` now implements an optional bounded
DeepSeek evidence-suggestion service. It requires the trusted stored packet,
loads only the owned session's observations/transcript/defense, checks observation
payload digests, and accepts a caller-supplied frozen diff. Its input is bounded
at 18,000 characters and output at 600 tokens. Every actual call reserves the same
persistent trial, global, user and session budgets before one provider request;
there are no automatic retries. Only the configured DeepSeek Flash endpoint/model
is accepted. Missing credentials, kill-switch/budget denial, provider failure,
invalid JSON, fabricated evidence IDs, or numeric score fields produce pending
review. Valid output is explicitly unverified suggestions for a human; it cannot
create final scores or authenticate correctness. The trusted caller must persist
its domain transaction before invoking the service because budget reservations
commit independently. Candidate text remains untrusted and model filtering is
not a guarantee against persuasive or incorrect observations.

`services/interview/grading_calibration.py` provides an operator pilot workflow:

```sh
PYTHONPATH=backend .venv/bin/python -m app.services.interview.grading_calibration --template --output /tmp/pilot-template.json
PYTHONPATH=backend .venv/bin/python -m app.services.interview.grading_calibration /path/to/trusted-review-export.json --output /tmp/calibration-report.json
```

The template lists all ten registered challenges and explicitly marks every anchor
set pending independent validation. It contains no manufactured pilot attempts.
An input export contains `records`, with one record per actual independently rated
attempt. Each requires `attempt_id`, `challenge_slug`, `challenge_version`,
`rubric_version: "v3-evidence"`, `synthetic: false`, `external_verified: true`,
`snapshot_digest`, `packet_digest`, `evaluator_version`, `inventory_digest`,
`ai_available`, and exactly two `reviews`. Each review requires an authenticated
`reviewer_id`, `reviewer_kind: "human"`, the matching `packet_digest`, and `ratings`
containing every applicable rubric dimension with integer values from 0 to 4.
This import validates structure and consistency, not the authenticity of assertions:
export it from trusted review/evaluator audit logs, never candidate submissions.

Reports include per-dimension confusion tables, exact agreement, quadratic weighted
Cohen kappa, exploratory paired bootstrap 95% intervals, and disagreements larger
than one rating anchor. At least 30 actual attempts per challenge, kappa >= .70,
and <=5% large disagreements are the initial engineering agreement gates. Undefined
kappa, missing ratings, duplicated attempts, same-reviewer pairs, model-only reviews,
synthetic data and unverified correctness fail closed. Mixed challenge/evaluator/
inventory versions or AI-opportunity cohorts cannot satisfy one release gate.
Insufficient data is a pending validation result, not evidence of poor candidate
performance. `agreement_gate_met` is separate from `release_ready`: agreement alone cannot
prove security, fairness or hiring validity. A report becomes release-ready only
when its statistical gates pass and a protected operator audit JSON attests completed
challenge/mutant validation, adversarial tenant isolation, reviewer authenticity,
measurement review, accessibility/fairness assessment, and matching inventory versions
for every registered challenge. Each audit requires nonempty evidence references.
Use `--audit-evidence /path/to/protected-audits.json` with the reporting command.

The operator audit format contains `challenge_and_mutant_validation`,
`adversarial_tenant_isolation`, `reviewer_authenticity`, `measurement_review`, and
`accessibility_and_fairness`, each with `completed: true` and `evidence_refs` listing
actual independent audit artifacts. Its `inventories` object must map each of the ten
challenge slugs to `challenge_version`, `evaluator_version`, `inventory_digest`, and
`evidence_ref`, matching the pilot records. This attests completed work; inserting
booleans without conducting the audits is not validation.

Publication remains default-off through `grading_publish_reviewed_scores`. When
enabled, `publication_allowed()` reads the protected local
`grading_calibration_report_path`, recomputes gates from the included original
records, verifies the SHA-256 dataset digest, and rejects missing or modified data.
Candidate and HTTP-uploaded files must never control this path. The current project
has no real calibration dataset or completed independent audit evidence, so reviewed
score publication remains blocked.

A protected operator can export persisted paired reviews directly, avoiding manual
assembly of rating/binding fields:

```sh
PYTHONPATH=backend .venv/bin/python -m scripts.export_grading_calibration --confirm-real-pilot --output /tmp/trusted-review-export.json
```

Use `--confirm-real-pilot` only after confirming the attempts came from actual pilot
participants rather than engineering fixtures. Without that attestation the export
contains no attempts. The exporter verifies signed evaluation provenance and frozen
source integrity via the trusted review service, requires current deployed challenge/
evaluator/inventory versions, and selects the earliest complete review from two
distinct authenticated staff reviewers against the same evidence packet and source.
Candidate self-reviews, invented reviewer identities, stale reviews, missing pairs,
and unverified execution are excluded with counts. It emits no submitted source,
transcripts, email addresses or names, and creates its output with owner-only file
permissions. Reviewer IDs remain pseudonymous sensitive pilot data.

Distinct reviewer identities do not alone establish independence or blinding.
Organize separate blinded rating sessions before collecting pilot records, and cite
that procedure in the independent reviewer-authenticity audit. The staff review
history can expose earlier ratings, so the current operational workflow does not
prove that reviewers were blinded. Exporting real data does not manufacture an
agreement gate or validate a hiring assessment. Publication additionally requires
pilot inventory versions to match the currently deployed evaluator and registry;
changing a challenge, evaluator, or inventory invalidates older readiness reports.

Candidate report requests recompute agreement/readiness gates without resampling
confidence intervals. Bootstrap intervals are generated by the offline operator
report workflow; the online projection marks them `offline_report_required`.
This preserves the same publication gates while avoiding expensive bootstrap work
inside the application request loop.
