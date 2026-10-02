# Webhook Delivery Retry

## Scenario
Webhook worker retries on 5xx; finance sees duplicate charges; staging melts under batch flush.

## Steps
The task opens one step at a time. Run the tests, then open the next step.

## Getting started
```bash
npm install
npm test
```
