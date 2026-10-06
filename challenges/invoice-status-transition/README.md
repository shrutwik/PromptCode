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
