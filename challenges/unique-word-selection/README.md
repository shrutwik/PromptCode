# Unique word selection

A subset validator rejects legal smaller answers and accepts repeated characters. Repair legality, find an optimum, and explain scaling without overstating complexity.

## Contract

Words are lowercase a–z strings; empty strings are allowed. A selection contains distinct input indices in range; concatenated words must contain no repeated character, including within a word. A legal suboptimal selection is still legal. choose returns sorted indices maximizing total characters; ties prefer fewer selected words, then the lexicographically smallest index list. Empty input returns []. Repeated equal words remain separate occurrences. Nonalphabetic input raises ValueError. Input lists remain unchanged. Return an exact answer; no time-based greedy cutoff.

## Getting started

```sh
pip install -r requirements.txt
pytest -q
```

Start with README.md, contracts.py, engine.py and tests/test_engine.py. Preserve public signatures and the frozen tests. For extra experiments use a candidate-owned scratch.py. Do not change runner configuration to obtain a pass.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Legality differs from optimality; index identity and deterministic ties are part of the objective.

### Part 1 — Validate independently

Repair legality for selected occurrences, internal duplicates, invalid characters and empty inputs.

Evidence to show:

- Selected indices are distinct and in range; each character occurs at most once.

### Part 2 — Find an exact optimum

Implement compatible-mask search with fewer-word then lexicographic ties, including duplicate occurrences.

Evidence to show:

- Maximize character count exactly, then prefer fewer words and lexicographically smaller indices.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- An exact optimum must beat a tempting overlapping word and omit useless empty words.

### Part 4 — Changed requirement — optional discussion

Give each word a value and maximize total value instead of unique character count. Show why keeping the fewest-word representative for a mask may no longer be a valid dominance rule.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
