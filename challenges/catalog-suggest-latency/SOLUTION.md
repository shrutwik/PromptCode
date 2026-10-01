# SOLUTION — catalog-suggest-latency

## Root cause
`suggest` does an n² catalog walk and records `catalog.length` scans per product.

## Investigation path
Failing latency/scan tests → nested loop in `suggest.ts`.

## Reference implementation
```ts
export function suggest(catalog: Product[], query: string, opts: SuggestOptions = {}): Product[] {
  const limit = opts.limit ?? 10;
  const queryTokens = query.toLowerCase().trim().split(/\s+/).filter(Boolean);
  const scored: { score: number; product: Product }[] = [];
  globalCounter.recordScan(catalog.length);
  for (const product of catalog) {
    const score = scoreProduct(queryTokens, product);
    if (score > 0) scored.push({ score, product });
  }
  scored.sort(compareRank);
  return scored.slice(0, limit).map((s) => s.product);
}
```

## Wrong alternatives
Cheat ranking; remove counter; wrong cache key.

## AI failure modes
1. Leave n² loop, add useless memoization.
2. Change ranking to go faster.

## Edge cases
Empty query; id tie-break.

## Verification
`npm test`

## Complexity
Medium, 25–35 min.

## Expected Event Timeline
| t | Event |
|---|---|
| 0–5 | Fail perf tests |
| 5–15 | Find n² |
| 15–25 | Single-pass fix |
| 25–35 | Confirm ranking |

## Positive signals
Preserves compareRank; respects counter contract.

## Negative signals
Deletes tests.

## Recovery signals
After cache attempt, fixes loop.

## Interviewer Observations
Treats counter as contract.

## Rubric (100)
| ID | Criterion | Pts |
|---|---|---|
| A | Remove n² | 25 |
| B | <200ms | 20 |
| C | Scan budget | 15 |
| D | Ranking preserved | 20 |
| E | No test sabotage | 10 |
| F | Explanation | 5 |
| G | Scope | 5 |

## Derived Timeline Metrics
Hot loop <12m; green <30m.

## Defend-Your-Code (4)
1. Q: Why not cache first? A: Fix complexity.
2. Q: One scan of n? A: Models one full read.
3. Q: Indexing? A: Optional later.
4. Q: Verify ranking? A: Deterministic test.
