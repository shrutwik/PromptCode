# Search suggest

You are on catalog search. Shoppers typing in electronics wait long enough that suggest feels hung.

Product will ship a faster list only if it ranks the same products in the same order as today. The catalog in this repo is in memory, about 10,000 products, with id, title, category, popularity, and tokens.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

`suggest` stays in the current rank order: higher score, then higher popularity, then id ascending.

On the 10,000-product catalog the tests build, a query finishes in under 200ms and the scan counter stays under 20,000.

A cache in front of suggest is a hypothesis. Measure the work a query does before you add one.

## Getting started

```bash
npm install
npm test
```
