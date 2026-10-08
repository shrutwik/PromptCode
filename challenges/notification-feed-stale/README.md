# Notification feed

You are on the notification feed. A user marks an item read and the unread badge stays. Two quick marks are worse: one of them disappears, and the badge does not match the rows.

Support has a screenshot of a badge that says 2 while the visible rows say read.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

The unread count is how many notifications have `read` set to false. After the feed loads, the badge shows that count.

Marking one item read leaves that row read and drops the badge by one. Marking two items read together leaves both rows read, and the badge matches when both calls finish. A row that was already read stays read.

Someone says the React list key is wrong. That is a hypothesis.

## Getting started

```bash
npm install
npm test
```

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Each async completion merges into current state and must converge with rendered rows and badge.

### Part 1 — Establish observable state

Reproduce one mark and verify both stored read state and the rendered count, including already-read rows.

Evidence to show:

- Stored read state and rendered badge agree after one action, including an already-read row.

### Part 2 — Merge concurrent successes

Repair two distinct and repeated quick actions without replacing another action’s update.

Evidence to show:

- Distinct and repeated concurrent successes converge without overwriting another action’s update.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- A failed concurrent mark must not erase two successful independent updates.

### Part 4 — Changed requirement — optional discussion

A refresh started before a mark completes afterward. Define request-generation or merge semantics and prove a stale response cannot undo a successful mark; discuss which server guarantees are needed.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
