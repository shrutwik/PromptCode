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

## Parts and reviewer evidence

An optimization may change work performed but must preserve the entire ranking and current data.

- Part 1 (Establish ranked parity): ranking-ties, no-match-and-limit, empty-query-and-zero-limit.
- Part 2 (Reduce measured work): large-catalog-ranking, multi-token-no-input-mutation.
- Part 3 (Pressure-test the model): changed-catalog-parity.

Part 3 checks this contract property: A repeated query against changed data must reflect the new ranked winner and preserve prefix limits. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: Query text alone is sufficient cache identity even when the supplied catalogue changes. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: Add indexed catalogue updates or a query cache. Define invalidation/version ownership and show a changed-product query that detects stale results; counters still require independent review. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Why not cache first? A: Fix complexity.
2. Q: One scan of n? A: Models one full read.
3. Q: Indexing? A: Optional later.
4. Q: Verify ranking? A: Deterministic test.

## Deeper assessment insight

Optimization changes work performed while preserving the complete ranked output and untouched input.

Compare score/popularity/id ties, normalized multi-token queries, zero limit, and operation counts before interpreting timing.

Plausible wrong repair: A stale query cache or a dishonest scan counter can look fast while violating the contract. Ask the candidate for a concrete failing example, not just an assertion that the shortcut is bad.

Changed requirement: Discuss cache invalidation when products change, using a changed-catalog example; caching is not automatically the repair. Keep this separate from baseline scoring and record the candidate reasoning and verification evidence.
