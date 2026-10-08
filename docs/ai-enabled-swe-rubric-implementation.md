# Research-informed rubric implementation

Implemented locally October 8, 2026. Rubric version: `v4-research-pilot`.

## Changes

- Weights: correctness 30, framing/investigation 15, implementation quality 15, AI judgment 10, verification 20, explanation/ownership 10.
- Criterion-specific 0–4 anchors are shared by the backend, candidate brief and reviewer interface.
- Challenge detail includes public criteria without private evaluation cases or answer guides.
- Reviewer evidence includes each question's existing invariant and baseline parts. The fourth optional discussion stays ungraded.
- AI permission, optional-use policy, observed prompts/responses and assessment mode are recorded in the evidence packet. Lack of interaction does not establish unavailability; availability remains unknown when no usable response was observed.
- Reviewed reports explain AI-dimension exclusion and adjusted-total limitations.
- Reports explicitly flag unmet independent behavioral requirements or manual coverage requirements beside the total. Existing correctness caps and evidence requirements remain enforced; these flags do not invent universal hiring cutoffs.
- New scoring and calibration use the new version. Historical stored scores and packets are not rewritten; an old packet cannot be scored with the new weights.
- Human review, verified external evaluation, source/digest binding, self-review prohibition and calibration publication gates remain intact.

## Verification

154 backend tests passed, with 3 environment-dependent live-database tests skipped, across grading, challenge API and optional-part tests. A subsequent all-twenty guidance check also passed. Ten frontend tests passed across candidate brief, reviewer anchors and reports. Core rubric/guidance lint, JavaScript syntax and whitespace checks passed. A broader lint invocation encountered existing route/style findings outside this change; unrelated cleanup was not performed.

The API test verifies serialized weights and anchors; the mixed-rating test distinguishes the new weights from the old ones. Workflow tests verify requirement flags, provenance and reviewer restrictions. Historical-packet and no-AI tests verify version rejection and honest missing-evidence behavior.

## Boundaries

This implements the adopted rubric in the existing practice-review flow. It does not claim predictive validity, enable uncalibrated score publication, change test-family weights, create a mandatory AI task, or turn optional discussion into a graded stage. Actual uptime, usability throughout a session and infrastructure retry policies cannot be inferred from response logs alone; the packet records only what is known.

No commit, push or deployment was performed in this implementation pass. Existing unrelated workspace changes were preserved.
