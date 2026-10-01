# Challenge revision workflow

1. Observe signals (completion, time, feedback, infra, human disagreement) — do not auto-edit scoring.
2. Open challenge folder under `challenges/<slug>/`; bump registry `version` when behavior changes.
3. Update README/tests/SOLUTION as needed; keep SOLUTION out of candidate workspace.
4. Run challenge tests locally; update `docs/beta-changelog.md`.
5. Deploy; new sessions get new `challenge_version`. Historical sessions keep prior version.
6. Scoring algorithm changes → bump `scoring_version` (e.g. v2), document, test — never rescore history silently.
