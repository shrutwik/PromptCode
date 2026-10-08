# Card triples

A strategy selects nonexistent or repeated physical cards. Repair move validation, implement a deterministic chooser and compare it with an exhaustive small-table oracle.

## Contract

Cards are dictionaries {id,amount}; ids are unique strings, amount is an integer 1..9. A legal move contains exactly three distinct current ids summing 15; equal amounts on different cards are allowed. legal returns False for a malformed move and validates the table first. choose returns the lexicographically smallest sorted legal id triple or None. remove returns a new table after a legal move, preserving order and input; illegal moves raise ValueError. Do not replace physical identity with value equality. Strategy-quality comparisons beyond correctness are discussion-only and require a separately stated scoring metric.

## Working checkpoints

1. Repair identity and multiplicity validation.
2. Implement a deterministic legal chooser and safe removal.
3. Compare with the exhaustive oracle; explain a changed scoring objective without silently changing legality.

These are checkpoints within one ticket; all stated contract requirements belong to the baseline. Use the provided assistant for scoped work, check its suggestions against the files, and explain one plausible wrong approach you rejected. A passing run is evidence for its cases, not proof of every possible input.

## Getting started

```sh
pip install -r requirements.txt
pytest -q
```

Start with README.md, contracts.py, engine.py and tests/test_engine.py. Preserve public signatures and the frozen tests. For extra experiments use a candidate-owned scratch.py. Do not change runner configuration to obtain a pass.
