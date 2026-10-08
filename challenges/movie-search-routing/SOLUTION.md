# SOLUTION — movie-search-routing

## Reference approach and limits

Use one parser/serializer contract at the browser and HTTP boundaries. Compose predicates before pagination; keep the filtered total. URL changes drive inputs and requests, while generation/cleanup rejects stale responses. A detail API alone is insufficient: direct browser routes must serve the shell and rendered detail/404 must work. The correctness implementation scans and sorts O(n log n); indexing is an optional discussion, not a substituted baseline.

Reviewed implementations are in backend/tests/ranked_reference_fixtures.py and remain interviewer/test-only.

## Initial incident

`src/queryState.ts` contains the faulty change `||(!v.genre||m.genre===v.genre)`. Repair the contract rather than changing expectations.

The candidate also restores stale-request rejection in MovieApp.tsx.

## Independent evidence

Eight server-owned observation probes cover this family; expected values never enter the candidate command. Two plausible wrong repairs are checked separately. Rendered frontend behavior retains explicit reviewer requirements even when the visible suite passes.

## Rubric (100)

Correct behavior and preservation: 35; model and explanation: 25; independent verification: 20; AI-output review and trade-offs: 20. This guide does not replace the platform rubric.

## Parts and reviewer evidence

The URL is canonical view state; filter/sort/count/page order and request identity must agree across browser and API.

- Part 1 (Repair query semantics): and-filters, year, literal-query, invalid-page.
- Part 2 (Integrate browser routes): page-after-filter, reset-page, detail-http, direct-shell.
- Part 3 (Pressure-test the model): combined-filter-page-http.

Part 3 checks this contract property: All three filters must compose before sort, total and page selection at the HTTP boundary. A behavioral pass observes these cases; it does not certify the candidate’s explanation. Existing declared manual review gaps remain.

Plausible wrong assumption to challenge: Paginate first and then filter, or report page length as the filtered total. Ask for a concrete counterexample; the selected automated wrong-repair fixtures remain the declared regression evidence.

Optional changed requirement: The catalogue changes between pages. Compare snapshot tokens or cursor pagination with numeric offsets; define ordering and URL behavior before promising stable traversal. This is discussion-only and must not silently become a baseline coding requirement.

## Defend-Your-Code (4)
1. Q: Where does filtering belong relative to pagination? A: Apply all predicates, sort, count and then page; paging first loses matching records and gives the wrong total.
2. Q: How many times is q decoded? A: Exactly once by URLSearchParams; applying decodeURIComponent again corrupts literal percent sequences.
3. Q: What makes refresh and back navigation consistent? A: The URL drives inputs and requests, including popstate; component-local filter state cannot be the only source.
4. Q: What stops an old request from overwriting new results? A: A request generation/active effect guard checks identity before publishing rows, errors or loading completion.
