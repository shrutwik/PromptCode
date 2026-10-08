# Search and routes

Repair the supplied movie app and Express API. Case-insensitive title substring, exact genre and minimum-year filters combine with AND, before stable id-ascending sort and pagination of size two; return rows and total matching count. URL query is canonical UI state. Decode q exactly once via URLSearchParams; encode through the inverse serializer. Missing q/genre means empty, missing minYear means null, missing page means one; page must be a safe positive integer written as decimal digits without leading zero, minYear four digits 1000..9999. Invalid query returns HTTP 400. Filter changes reset page to one; refresh and popstate hydrate inputs and results from URL. GET /api/movies/:id returns the movie or 404. Direct /movies/:id and /movies serve the HTML app shell; React shows the loaded detail or Not found. Show loading/error state; an older request must not replace results for a later URL. Inputs/dataset stay unchanged. Unknown genres are allowed and match nothing.

## Verification

Run `npm test`. Start with the listed entry files and tests; starters intentionally contain a defect. A passing suite is evidence, not a substitute for explaining the invariant.

## Browser preview

Install the locked dependencies with `npm ci`, then run `npm run dev` and open the printed local address. Run `npm run dev:api` in a second terminal; the Vite development server forwards /api calls to Express on port 3001. Direct /movies/id browser routes use the Vite app-shell fallback. The frozen `npm test` command remains the acceptance suite.

## Interview parts

Parts 1–3 organize the existing baseline contract; complete them in one ticket. The full suite remains the acceptance bar. Part 4 is discussion-only, has no extra coding requirement and does not affect the automated behavioral score.

Underlying invariant: The URL is canonical view state; filter/sort/count/page order and request identity must agree across browser and API.

### Part 1 — Repair query semantics

Combine all filters, decode literals once and reject invalid pages before serving results.

Evidence to show:

- All filters combine before paging; literals decode once and invalid numeric queries return 400.

### Part 2 — Integrate browser routes

Hydrate refresh/back state, reset pages, serve direct detail routes and retain latest-request loading/error/result ownership.

Evidence to show:

- URL state hydrates refresh/back, detail/404 routes work, and stale responses cannot own current rows/errors/loading.

### Part 3 — Pressure-test the model

Run the added fixture, then construct a second input exposing the same incorrect assumption. Explain the expected outcome before accepting a proposed AI repair.

Evidence to show:

- All three filters must compose before sort, total and page selection at the HTTP boundary.

### Part 4 — Changed requirement — optional discussion

The catalogue changes between pages. Compare snapshot tokens or cursor pagination with numeric offsets; define ordering and URL behavior before promising stable traversal.

Evidence to show:

- Identify the changed invariant, affected code/data, and a minimal counterexample before proposing an implementation.

Keep supplied tests and runner files intact. Show observed verification and one AI suggestion you checked or rejected; use scratch files for additional experiments. Explanations require reviewer judgment; a passing behavioral run does not certify understanding.
