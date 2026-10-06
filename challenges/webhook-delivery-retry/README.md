# Webhook retry

You are on outbound webhooks. Receivers sometimes answer 500, and the worker retries. Finance then sees the charge recorded twice for one delivery. A flush of the pending queue also made staging fall over.

Delivery is at-least-once. A retry after a 5xx is normal. The side effect has to survive that.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

A delivery that fails and then succeeds still records the charge once for that delivery id. Attempts stop at the retry policy’s max.

Flushing a batch keeps at most about five posts in flight at once.

Lowering the timeout is a hypothesis. The duplicate charge is the incident.

## Getting started

```bash
npm install
npm test
```
