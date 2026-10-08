# Invoice status

You are the billing engineer on call before month-end close.

Finance collected invoice `inv_paid`, then this service showed it as draft. Draft is the editable state. A paid invoice that looks like a draft can change after money has moved.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

A paid invoice stays paid unless it is voided. Void keeps the paper trail.

These moves still succeed: draft to sent, draft to void, sent to paid, sent to void, and paid to void. Void is terminal. A status moved onto itself is not a transition.

`POST /invoices/:id/transition` returns 409 when the move is illegal, including sent back to draft, and the stored status stays as it was. A missing invoice is a different failure from an illegal move.

Statuses are `draft`, `sent`, `paid`, and `void`. Amounts are integer cents.

A teammate says last sprint’s date formatter rewrote the status. That is a hypothesis.

## Getting started

```bash
npm install
npm test
```

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: Transition legality is a directed graph; rejected writes preserve the entire stored invoice.

### Part 1 — Establish the legal graph

Enumerate every state pair and distinguish an illegal transition from an absent invoice.

Evidence to show:

- Every state pair matches the legal graph; missing resources and illegal moves are distinct.

### Part 2 — Apply legal lifecycle changes

Repair API/service transitions while preserving customer, money and issued identity.

Evidence to show:

- Legal lifecycle transitions preserve money/customer identity; the complete invoice remains unchanged on rejection.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- The complete legal lifecycle must end in a terminal state whose rejected edit preserves every field.

### Part 4 — Changed requirement — optional discussion

Two users attempt different transitions from the same revision. Design a compare-and-set/version check and explain which loser receives a conflict without overwriting the winner.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
