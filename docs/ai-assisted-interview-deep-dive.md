# AI-assisted coding interviews: detailed questions, contracts and tests

> Historical research/ranking snapshot before the October 7 expansion. For the implemented twenty-question library and verified coverage, see [the implementation report](interview-library-expansion.md).

Research checked October 7, 2026. This expands the [original question bank](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-question-bank.md) into **38 exercises**: **28 original practice specifications** and **10 existing PromptCode challenges**. The practice specifications contain **224 concrete input/expected-result scenarios**. The [local appendix](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-local-tests.md) reproduces the candidate instructions, visible tests, fixtures, and all **62 trusted behavioral probes** with exact expected results. The [JSON catalogue](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-catalogue.json) contains the same structured material for importing into a question library.

No search can cover the entire internet, and no employer-private test suite or starter repository was obtained. The 224 practice scenarios are **newly authored contracts and test designs**, not discovered hidden tests and not executable test implementations. Public practice pages expose some filenames, stages and test identifiers; their full staged assertion code was inaccessible. Local source is exact for this workspace snapshot. All uncertainty is retained rather than filled with invented employer details.

## What interviewers appear to be asking you to demonstrate

The recurring theme is engineering ownership with AI available: understand the existing contract, diagnose a failure, make a coherent change, verify it and explain the result. That interpretation follows [Canva's official description](https://www.canva.dev/blog/engineering/yes-you-can-use-ai-in-our-interviews/) and [HackerRank's design guidance](https://www.hackerrank.com/blog/how-to-interview-engineers-who-use-ai-coding-assistants/); it is not a universal scoring rubric.

| Type | Typical request | What is being assessed | Appropriate starter repository | Strong verification |
|---|---|---|---|---|
| Incident/debugging | The endpoint succeeds but the data disappears | Request tracing, root cause, state preservation | Runnable service and client with a focused defect | Reproduce → mutate → independently read; injected write failure |
| Progressive algorithm | Fix validator, solve baseline, extend constraints | Modeling, correctness, adapting an algorithm | Parser/model/validator plus baseline solver | Small oracle, unreachable cases, tie rules, changed-state cases |
| Feature delivery | Build a small editor or extend six features | Scope judgment, integration, usable demo | Bootable frontend, API interfaces and fixtures | UI interaction sequences and persistence round trips |
| Stateful/concurrent system | Retry, reserve, cache or mark items atomically | Identity, race analysis, idempotency | Fake clock, injected storage, synchronization seams | Controlled interleavings and final state, not sleeps |
| Performance | Preserve ranking while reducing work | Profiling, invariants, complexity | Slow reference implementation and generated data | Golden output parity plus operation counts and calibrated timing |
| Safe refactor | Extract a rule loop without changing results | Behavior preservation and abstraction direction | Existing working golden fixtures | Exact cents/order parity plus source review |
| Strategy evaluation | Improve game choices or recommendations | Validity versus quality, metric design | Engine, seeded fixtures, baseline strategy | Legal output on every run; shared seeds/held-out data |
| Contract diagnosis | A test disagrees with intended behavior | Evidence, restraint, ability to challenge AI output | Written contract, suspect assertion, small consumer | Independent regressions that distinguish permissive from correct |

AI access is itself a constraint to record before starting. [HackerRank's current candidate guide](https://candidatesupport.hackerrank.com/articles/6665907643-ai-assistant-in-interviews) distinguishes guarded single-file help from repository Agent/Plan support, when enabled by the hiring company; interviewers can see interactions. [LinkedIn's policy](https://careers.linkedin.com/Howwehire/ai-usage) also makes permission interview-specific. A practice website's AI stage badges do not establish an employer's policy.

## Reported questions: what is known and what is missing

| Source and evidence | Task actually described | Detail available | Detail not established |
|---|---|---|---|
| [Meta E4 account](https://www.reddit.com/r/leetcode/comments/1p35b98/meta_e4_software_product_interview_experience/) — anonymous firsthand | Maze graph/serialization, BFS, walls and portals in stages | Theme and staged progression | Exact graph schema, portal cost, assertions, complete starter |
| [Microsoft SDE2 account](https://www.reddit.com/r/leetcode/comments/1sfgtu3/ai_assisted_coding_interview_experience_microsoft/) — anonymous firsthand | Load balancing with two heaps, AI use and explanation | Algorithm family; that interview restricted pasting the whole prompt | Precise dispatch/drop policy and test values; a GitHub rebuild was recruiter guidance |
| [Amazon repository OA](https://www.reddit.com/r/amazonemployees/comments/1tj88m7/amazon_sde1_oa_new_format_with_an_ai_assistant/) — anonymous firsthand | Three web-app bugs, preview plus repository | Reported 60-minute repo portion; several backend stack choices | Actual three fixtures or a universal Amazon format |
| [Amazon MovieDB account](https://www.reddit.com/r/amazonemployees/comments/1vhkpas/amazon_backend_oa_questions_2026_greedy_coding/) — firsthand, promotional link present | Watchlist persistence, rate limiting, password validation | Failure themes | Numerical limits, endpoint schemas, concurrency and hidden tests |
| [Amazon Glassdoor submission](https://www.glassdoor.com/Interview/You-are-given-a-full-web-application-codebase-frontend-and-backend-Identify-and-fix-bugs-including-broken-search-filter-QTN_8998301.htm) — anonymous submission | Search/filter and routing fixes in full-stack code | Broad affected flows | Dataset, route definitions and assertions |
| [Canva frontend notes](https://www.reddit.com/r/cscareerquestionsOCE/comments/1t1jfxx/canva_interview_notes/) — firsthand plus comment | Small design editor; separate commenter reports a team portal | Primitive shapes/toolbar/editor theme | Our storage, undo, portal-search and permissions requirements |
| [Atlassian thread](https://www.reddit.com/r/leetcode/comments/1wpb4da/atlassian_ai_enabled_interview/) — anonymous comment, attribution disputed in replies | Configurable logger, plan/design followed by demo; another comment mentions staged maze work | Indexed replies describe a vague short prompt and candidate-provided boilerplate | Employer attribution is unverified; no assertion code |
| [Rippling AI-permitted account](https://leetcode.com/discuss/post/7649290/) — firsthand, promotional link present | Food Deliveries and Card Game | Names of received themes | Exact accounting/game contract; other listed practice tasks were recommendations |
| [Separate Rippling delivery account](https://leetcode.com/discuss/post/7602654/rippling-sde1-interview-experience-compe-dmgj/) — firsthand | Driver registration, earliest-available trip booking, hourly cost, driver-count extension | More delivery-domain detail | This separate account does not establish that its round allowed AI; do not merge its exact prompt into the other report |
| [Frontend discussion](https://www.reddit.com/r/Frontend/comments/1rk9d65/frontend_interviews_in_the_age_of_ai/) — anonymous comment | Six features in an existing repo within an hour | Feature count and repo format | Employer and six specific features; our dashboard is invented |
| [Meta E6 account](https://www.reddit.com/r/leetcode/comments/1qxwwh5/sharing_my_meta_e6_mle_interview_experience/) — firsthand | Correct test/method alignment, then solve and compare strategies | Stage theme | Exact algorithm and expected outputs; our parser example is invented |
| [Canva engineering article](https://www.canva.dev/blog/engineering/yes-you-can-use-ai-in-our-interviews/) — official | Airport-control illustration | Official example of ambiguity and AI-assisted engineering | Not confirmed as the question a candidate received |

A [Meta convolution account](https://www.reddit.com/r/leetcode/comments/1reuwrd/meta_ai_coding_interview/) distinguishes AI coding from AI-enabled coding, so it is excluded as evidence for permitted-assistant interviews. Reposts and commercial company tags do not independently authenticate a question. No reliable frequency ranking can be calculated from these self-selected accounts.

## Public practice examples: exposed stage and test inventory

These thirteen examples are primary evidence for **what the practice publisher offers**, not proof of an employer's question bank. Only visible first-stage test names and public stage summaries were obtained. The full later-stage workspace was subscription-gated; no bypass was attempted. Names identify intent but do not reveal complete setup, assertion values or coverage. Requirements below each original exercise explicitly resolve missing details for practice use.


| Public example | Exposed Python files (excluding support files) | Public stage sequence | Our exercise |
|---|---|---|---|
| [Maze](https://algo.monster/ai-coding-interview/maze_solver) | main.py, maze.py, mazes.py, solver.py | rendering → solver → directional edges → keys/doors | 1–3 |
| [Unique characters](https://algo.monster/ai-coding-interview/max-unique-characters-subset) | max_unique.py, subset_utils.py | validator → solver → bigger inputs → full dataset | 18 |
| [Sum-15 cards](https://algo.monster/ai-coding-interview/card-game-15-opt) | engine.py, pieces.py, strategies.py | validator → baseline → measurement → improvement | 31 |
| [Friend recommendation](https://algo.monster/ai-coding-interview/friend-recommendation) | recommenders.py, social_graph.py | validator → baseline → measurement → improvement | 32 |
| [Compiler cost](https://algo.monster/ai-coding-interview/compiler-optimization) | compiler_optimizer.py, optimizer_utils.py | metadata → analyzer → dead code → constant folding | 33 |
| [Delivery dashboard](https://algo.monster/ai-coding-interview/delivery-cost-dashboard) | delivery_dashboard.py, delivery_models.py | duration precision → live totals → payment cutoff → peak drivers | 12 |
| [Dependency impact](https://algo.monster/ai-coding-interview/service-dependency-impact) | path_utils.py, service_dependency.py | normalize → direct impact → deleted subtrees → dependents | 34 |
| [Progressive LRU](https://algo.monster/ai-coding-interview/lru-cache-progressive) | lru_cache.py | recency → eviction → resize → atomic get_or_put | 15 |
| [Hand comparator](https://algo.monster/ai-coding-interview/card-hand-comparator) | card_hand.py, hand_utils.py | rank parsing → comparison → partial hands → rule extension | 13 |
| [Expense rules](https://algo.monster/ai-coding-interview/expense-rule-engine) | expense_engine.py, expense_rules.py | numeric amounts → item rules → trip/composite rules → scale | 37 |
| [Meeting scheduler](https://algo.monster/ai-coding-interview/meeting-scheduler) | booking_utils.py, scheduler.py | overlap → earliest slot → sorted bookings → atomic reserve | 35 |
| [Crawler queue](https://algo.monster/ai-coding-interview/crawler-frontier-queue) | crawl_queue.py, heap_utils.py | FIFO ties → push/pop → ready jobs → cooldown | 36 |
| [Contained strings](https://algo.monster/ai-coding-interview/shared-substring-in-string-list) | benchmark.py, substring_finder.py | one container → shortest → larger data → all pairs | 38 |

There are **40 publicly visible test identifiers** across these pages. They are reproduced as identifiers, not as complete tests:

**[Maze](https://algo.monster/ai-coding-interview/maze_solver)**: `test_render_with_path_preserves_start_and_end`, `test_render_with_path_marks_open_cells`.

**[Unique characters](https://algo.monster/ai-coding-interview/max-unique-characters-subset)**: `test_accepts_legal_but_suboptimal_selection`, `test_accepts_single_word`, `test_accepts_single_character_words`, `test_accepts_all_words_when_disjoint`, `test_rejects_internal_duplicate_word_accepts_clean_word`, `test_rejects_global_character_overlap_accepts_disjoint_words`, `test_rejects_words_not_in_input_accepts_listed_words`, `test_empty_selection_is_valid`.

**[Sum-15 cards](https://algo.monster/ai-coding-interview/card-game-15-opt)**: `test_rejects_card_not_on_table`, `test_rejects_using_same_single_card_twice`, `test_accepts_real_triple_from_table`.

**[Friend recommendation](https://algo.monster/ai-coding-interview/friend-recommendation)**: `test_rejects_self_recommendation`, `test_rejects_existing_friend`, `test_rejects_duplicates`, `test_accepts_clean_candidate_list`.

**[Compiler cost](https://algo.monster/ai-coding-interview/compiler-optimization)**: `test_reads_per_file_operator_costs`, `test_reads_multi_digit_metadata_values`, `test_ignores_comments_and_blank_lines_in_program_body`.

**[Delivery dashboard](https://algo.monster/ai-coding-interview/delivery-cost-dashboard)**: `test_ninety_minutes_is_not_truncated_to_one_hour`, `test_half_hour_uses_second_precision`.

**[Dependency impact](https://algo.monster/ai-coding-interview/service-dependency-impact)**: `test_collapses_repeated_slashes_and_trailing_slash`, `test_preserves_root_path`, `test_ancestor_check_uses_normalized_paths`.

**[Progressive LRU](https://algo.monster/ai-coding-interview/lru-cache-progressive)**: `test_get_refreshes_recently_used_key`.

**[Hand comparator](https://algo.monster/ai-coding-interview/card-hand-comparator)**: `test_parses_ten_as_a_two_character_rank`, `test_parses_face_cards`.

**[Expense rules](https://algo.monster/ai-coding-interview/expense-rule-engine)**: `test_amounts_are_compared_numerically`, `test_small_amounts_do_not_exceed_large_thresholds`.

**[Meeting scheduler](https://algo.monster/ai-coding-interview/meeting-scheduler)**: `test_touching_intervals_do_not_overlap`, `test_nested_intervals_overlap`, `test_partial_overlap_is_detected`.

**[Crawler queue](https://algo.monster/ai-coding-interview/crawler-frontier-queue)**: `test_earlier_sequence_wins_when_priority_matches`.

**[Contained strings](https://algo.monster/ai-coding-interview/shared-substring-in-string-list)**: `test_returns_container_for_example`, `test_returns_none_when_no_pair_exists`, `test_single_string_returns_none`, `test_duplicates_count_as_containment`, `test_is_case_sensitive`, `test_returns_a_valid_container_on_mixed_list`.

[Hello Interview](https://www.hellointerview.com/practice/ai-coding) also exposes a structured/open-ended practice catalogue, but accessible extracts did not provide test assertions. Its [overview](https://www.hellointerview.com/learn/ai-coding/overview/introduction) is useful format guidance, not an independent employer-test inventory.

## Detailed original practice specifications

Numbers 1–20 retain the original bank. Existing local challenges occupy 21–30 in the next section; new public-practice-inspired families are 31–38. Every following contract, fixture and expected result is authored for practice. Do not infer that the linked employer or publisher uses our numerical values, return schemas, tie policies or follow-up rules. Each starter is a proposed specification, not a created codebase.

### 1. Maze serialization and topology

**Candidate question:** Saving then loading a maze changes its topology. Repair the codec without changing its public interface.

**Exact practice contract:** Original contract: nodes have unique string ids and coordinates; edges are undirected and serialized once in sorted endpoint order; portals are separately identified directed links. Encode/decode preserves every node, edge and portal. Unknown references, duplicate ids and unsupported versions raise CodecError before publishing a partially loaded maze. Wall cells have no nodes. Version 1 is the only accepted version initially.

**Starter codebase:** Python models.py, codec.py, render.py; fixtures with isolated nodes and portals; test_codec.py. Supply a working model and renderer and a defective codec.

**Progression:** 1 reproduce a bad round trip; 2 preserve topology and reject corrupt references; 3 deterministic encoding; 4 introduce an explicit version migration.

**What can go wrong:** Dropping isolated cells; reconstructing adjacency from coordinates despite walls; turning a portal into an ordinary edge; partially mutating the model on errors.

**Algorithm and verification considerations:** O(V+E+P) decoding; canonical sorting adds O(E log E + P log P). Compare graph meaning rather than incidental JSON key order.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P01-01 | nodes A@(0,0), B@(0,1); edge A-B; encode then decode | same nodes and undirected adjacency A↔B |
| P01-02 | isolated A and B; no edges | both nodes retained; no inferred connection |
| P01-03 | nodes A,B; portal p: A→B | portal p retained with the same direction; no B→A portal inferred |
| P01-04 | edge A-Z with no node Z | CodecError; no partial loaded model |
| P01-05 | two nodes with id A | CodecError |
| P01-06 | same graph supplied with reversed node and edge order | identical canonical encoded representation |
| P01-07 | version=99 | CodecError: unsupported version |
| P01-08 | empty node/edge/portal lists at version=1 | valid empty maze; round trip remains empty |

**Debrief questions:** Why are connectivity and coordinates distinct? Which fields must survive a round trip? How would a version migration preserve old files?

### 2. Shortest paths, portals and rendering

**Candidate question:** Repair or implement a shortest route and render it without overwriting the entrance and exit.

**Exact practice contract:** Original contract: rectangular grid; # blocks movement, . is open, S/E mark endpoints; four neighbors in U,R,D,L order. Return coordinates including both endpoints; None means unreachable. A supplied start may equal the exit. Optional portal jumps are directed, cost one move and are considered after ordinary neighbors. Rendering marks internal route cells * but preserves S/E/#. Reject ragged grids or missing endpoints.

**Starter codebase:** Reuse maze models/codec; solver.py, render.py, test_solver.py and test_render.py; a working grid loader and known defective baseline.

**Progression:** 1 endpoint-preserving rendering; 2 BFS correctness; 3 directed passages; 4 portal-cost extension. These combine reported and public-practice themes, not an exact employer stage sequence.

**What can go wrong:** Visited state marked too late; DFS mistaken for shortest path; inconsistent portal cost; overwriting endpoints; nondeterministic neighbor iteration.

**Algorithm and verification considerations:** Unit-cost BFS O(V+E), memory O(V). Use 0–1 BFS for zero/one costs or Dijkstra for other nonnegative costs only if requirements change.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P02-01 | grid [S.E] | [(0,0),(0,1),(0,2)]; rendering S*E |
| P02-02 | grid [S#E] | None; rendering unchanged |
| P02-03 | grid [S.,.E] | [(0,0),(0,1),(1,1)] under U,R,D,L ties |
| P02-04 | open 2×2 grid; start=exit=(0,0) | [(0,0)]; zero moves |
| P02-05 | grid [S...,###.,E...] | [(0,0),(0,1),(0,2),(0,3),(1,3),(2,3),(2,2),(2,1),(2,0)] |
| P02-06 | grid [S#E]; portal (0,0)→(0,2) | [(0,0),(0,2)]; one move |
| P02-07 | grid [S#E]; portal (0,2)→(0,0) | None; reverse traversal forbidden |
| P02-08 | grid [S.,E] | validation error: ragged grid |

**Debrief questions:** What makes BFS correct here? Where is a node marked visited? How would zero-cost portals change the algorithm?

### 3. Keys, doors and stateful graph search

**Candidate question:** Extend the maze solver so key collection changes which doors can be traversed.

**Exact practice contract:** Original contract: lowercase a–f are reusable keys, uppercase A–F are matching doors (E is reserved for the exit, so key e/door E are not supported). A door requires its key before entry; collecting a key costs no extra move. Search state is (row,column,key_mask). U,R,D,L ties; return a shortest coordinate route or None. Directed edges constrain moves independently of keys.

**Starter codebase:** Same maze repository; tile parser, solver state representation, key-door fixtures and tests. Supply the stage-2 solver as a starting snapshot.

**Progression:** 1 parse keys/doors; 2 expand state and revisit coordinates; 3 shortest legal route; 4 introduce directed edges or consumable-key semantics explicitly.

**What can go wrong:** A visited set containing only coordinates; unlocking every door after any key; counting key pickup as an extra step; treating E as both a door and exit.

**Algorithm and verification considerations:** O(V·2^K + E·2^K) time and O(V·2^K) memory for K reusable key types. Consumable keys need a different state definition.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P03-01 | grid [SaAE] | [(0,0),(0,1),(0,2),(0,3)] |
| P03-02 | grid [SAE] | None; A cannot be entered |
| P03-03 | grid [aS.AE] | [(0,1),(0,0),(0,1),(0,2),(0,3),(0,4)] |
| P03-04 | grid [SbAE] | None; key b does not unlock A |
| P03-05 | grid [SaAbBE] | all six coordinates in order; both locks opened |
| P03-06 | grid [SaAAE] | all five coordinates in order; key a is reusable |
| P03-07 | grid [SAE,###,a..] | None; unreachable key is not collected |
| P03-08 | grid [SaAE]; edge (0,1)→(0,2) explicitly forbidden | None despite holding a |

**Debrief questions:** Show why revisiting a coordinate with a different inventory is necessary. Which dominance pruning is sound and which could destroy a shorter path?

### 4. Two-heap load balancing

**Candidate question:** Assign jobs to workers, retaining queued jobs and deterministic tie behavior.

**Exact practice contract:** Original contract: workers numbered 0..k−1; arrivals sorted by (arrival,input_index); duration is a positive integer; requests queue FIFO when no worker is free. Release completions with finish≤dispatch_time before selecting the smallest free worker id. Each output is (job,worker,start,finish). Reject k≤0 or invalid duration before scheduling.

**Starter codebase:** Python scheduler.py, models.py, fake clock, a slow reference simulator and fixtures; tests compare assignments rather than heap layout.

**Progression:** 1 clarify queuing versus dropping; 2 idle-id and busy-(finish,id) heaps; 3 simultaneous events; 4 weighted workers or cancellation.

**What can go wrong:** Releasing only one of several completed workers; finish<arrival instead of ≤; losing queued work; tie policy implicit in heap tuple order.

**Algorithm and verification considerations:** After sorting, O(n log k); O(k+n) output/storage. A simulator provides an independent oracle for randomized small workloads.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P04-01 | k=2; A(0,5),B(0,2),C(0,1) | A→0[0,5), B→1[0,2), C→1[2,3) |
| P04-02 | k=1; A(0,2),B(2,1) | A→0[0,2), B→0[2,3) |
| P04-03 | k=2; A(0,2),B(0,2),C(2,1) | C→0[2,3); both workers released before choice |
| P04-04 | k=1; A(0,3),B(1,1),C(1,1) | starts A=0,B=3,C=4; FIFO preserved |
| P04-05 | k=3; no jobs | [] |
| P04-06 | k=0; one job | validation error |
| P04-07 | k=1; duration=0 | validation error |
| P04-08 | k=2; A(10,1),B(10,1),C(12,1) | workers A=0,B=1,C=0; idle gap handled |

**Debrief questions:** Why two heaps? How are queued jobs ordered? Does a worker completing at t accept a job arriving at t?

### 5. Configurable logger and failure isolation

**Candidate question:** Build a configurable structured logger and demonstrate working output destinations.

**Exact practice contract:** Original contract: DEBUG<INFO<WARN<ERROR; threshold includes its own level. Records contain level,message,timestamp,context; context is copied at emission. Inject the clock and sinks. Unknown levels/configurations are rejected atomically. Default sink policy: continue to remaining sinks and return an error list; no recursive logging. Reconfiguration affects subsequent calls, not existing records.

**Starter codebase:** TypeScript logger.ts, config.ts, formatters.ts, sinks.ts, demo.ts; fake clock and in-memory/failing sinks. No filesystem permission assumptions in unit tests.

**Progression:** 1 requirements and interfaces; 2 threshold/formatting; 3 multiple sinks and failure policy; 4 runtime configuration or buffered writes.

**What can go wrong:** Severity order reversed; mutating caller context; errors swallowed invisibly; recursive failure logging; file streams left open.

**Algorithm and verification considerations:** O(S+C) per emitted record for S sinks and C context size; buffering requires explicit backpressure and shutdown-flush semantics.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P05-01 | threshold INFO; log DEBUG | zero sink writes |
| P05-02 | threshold INFO; log INFO hello at fixed time 100 | one record with INFO,hello,timestamp=100 |
| P05-03 | threshold ERROR; log WARN then ERROR | only ERROR emitted |
| P05-04 | two sinks; first throws; second captures | second receives record; result reports first sink failure |
| P05-05 | context {requestId:r1}; log; then mutate original to r2 | stored record retains r1 |
| P05-06 | configure level VERBOSE | configuration error; previous settings retained |
| P05-07 | threshold WARN; reconfigure DEBUG; log INFO | INFO now emitted once |
| P05-08 | message containing a newline and quote; JSON formatter | parseable JSON; original message recovered after parsing |

**Debrief questions:** What does successful logging mean if one sink fails? Who closes a file sink? How would secrets be redacted consistently?

### 6. Canvas editor and document state

**Candidate question:** Build a small shape editor with selection, movement, styling and persistence.

**Exact practice contract:** Original contract: shapes have unique ids,type,x,y,width,height,color; coordinates are in canvas space; toolbar insertion creates one shape, selection is by id, drag affects only the selected shape. Stored schema version=1; validate before replacing state. Undo/redo records completed actions, not every pointer movement. Failed loads preserve the current design.

**Starter codebase:** React Canvas.tsx, Toolbar.tsx, Inspector.tsx, designStore.ts, serialization.ts; pointer-event helpers, local-storage adapter and component tests.

**Progression:** 1 usable insertion/rendering; 2 selection and dragging; 3 styles and save/reload; 4 undo/redo or zoom-coordinate mapping.

**What can go wrong:** Using viewport coordinates after zoom/scroll; multiple shapes moving; stale selection; accepting malformed storage; pointer release outside canvas losing the drag.

**Algorithm and verification considerations:** Rendering O(n) without virtualization; id lookup O(1) with a map. History memory depends on snapshots versus commands and should be bounded.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P06-01 | insert rectangle into empty design | one rectangle with a unique id; selected id points to it |
| P06-02 | A@(10,20), B@(50,50); drag selected A by (5,−2) | A@(15,18); B unchanged |
| P06-03 | A selected; set color #112233 | only A color changes |
| P06-04 | save two shapes then reload version-1 document | same ids,positions,dimensions,colors and order |
| P06-05 | load width=−1 | validation error; existing design unchanged |
| P06-06 | delete selected A | A removed; selection cleared |
| P06-07 | insert A, drag A, undo then redo | undo restores pre-drag position; redo restores post-drag position |
| P06-08 | zoom=2; pointer moves 20 screen pixels horizontally | shape moves 10 canvas units horizontally |

**Debrief questions:** Where is the single source of truth? How do pointer coordinates become document coordinates? What constitutes one undo action?

### 7. Team portal and persistence

**Candidate question:** Add member search and persisted role editing to an existing portal.

**Exact practice contract:** Original contract: roles are member/admin; only a team admin may edit roles for their own team. Search is trimmed case-insensitive substring matching on display name; role changes require server acceptance before showing success. Unknown member→404, invalid role→400, unauthorized mutation→403; rejected mutations preserve stored state. Preserve the search query across a refresh.

**Starter codebase:** React MembersPage.tsx, MemberForm.tsx, api.ts; Express members route/service and seeded store; request and UI tests.

**Progression:** 1 understand API and UI state; 2 compose search and role editing; 3 errors and reload; 4 invitation or last-admin constraints if added explicitly.

**What can go wrong:** Updating only component state; missing authorization in the server; stale optimistic state after rejection; accidental edits to another team.

**Algorithm and verification considerations:** O(n) search in the small starter; query indexing and paginated APIs are follow-ups, not prerequisites.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P07-01 | members Alice,Bob; search " ALI " | Alice only |
| P07-02 | admin changes Alice member→admin then reloads | GET and UI both show admin |
| P07-03 | role=owner | 400; previous role retained |
| P07-04 | ordinary member changes another member role | 403; no mutation |
| P07-05 | admin for team T edits member of team U | 403; no mutation |
| P07-06 | save receives server 500 | error displayed; no success message; prior role retained |
| P07-07 | search zzz | empty-results state without an exception |
| P07-08 | open page with ?q=bob then refresh | search remains bob; Bob visible |

**Debrief questions:** Where must authorization live? What happens if a save fails? Can an administrator remove the last administrator under the stated contract?

### 8. Watchlist write/read round trip

**Candidate question:** An add action reports success but later reads omit the movie. Trace the full request path and fix persistence.

**Exact practice contract:** Original contract: unique (user_id,movie_id) membership; authenticated user derived from the token; first insert→201, repeat→200 with the same membership id. Unknown movie→404. Store failure→500 and no success state. GET reads committed membership for that user. Concurrent duplicate requests create exactly one membership.

**Starter codebase:** Spring Boot controller/service/repository/entity/DTO; React watchlist page and API client; integration database and injected-failure tests. Express or Django can implement the same exercise contract.

**Progression:** 1 reproduce add→GET; 2 trace DTO/service/transaction/store; 3 repair persistence; 4 duplicates and concurrent inserts.

**What can go wrong:** Saving a detached object; omitting repository write; reading a different store; trusting user_id from the body; hiding failed writes behind 200.

**Algorithm and verification considerations:** Unique constraint provides durable deduplication; transactions and exception handling must align with response semantics.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P08-01 | U adds existing M, then GET /watchlist | 201; GET includes M once |
| P08-02 | U adds M twice | statuses 201,200; same membership id; one row |
| P08-03 | U adds missing movie | 404; no membership inserted |
| P08-04 | U1 adds M; U2 reads watchlist | U2 list remains empty |
| P08-05 | unauthenticated add | 401; no write |
| P08-06 | repository throws before commit | 500; GET still empty; UI shows failure |
| P08-07 | two concurrent U/M adds | one membership row; one 201 and one 200 |
| P08-08 | authenticated U1 submits body user_id=U2 | membership belongs to U1; U2 remains unchanged |

**Debrief questions:** Which response proves a commit? How is uniqueness enforced under concurrency? Which layer caused the disappearing item?

### 9. Search/filter composition and deep links

**Candidate question:** Repair combined filters, refresh behavior and direct navigation in a movie application.

**Exact practice contract:** Original contract: case-insensitive title search; genre and minYear filters combine with AND. URL is canonical view state; q values are encoded/decoded once. Positive page numbers, page size=2, stable id ascending after filtering. A direct /movies/:id URL loads the record or a 404 screen. Missing/invalid filters are rejected or normalized according to the explicit parser, not silently interpreted differently by UI and API.

**Starter codebase:** React MovieList.tsx, queryState.ts, routes.tsx; search endpoint/repository; seeded movies and browser-route/request tests.

**Progression:** 1 API filtering correctness; 2 URL/UI synchronization; 3 refresh and deep links; 4 pagination and stale-response prevention.

**What can go wrong:** OR instead of AND; double URL decoding; filtering after pagination; client-only route fallback absent; page not reset on changed filters.

**Algorithm and verification considerations:** O(n) reference filtering for correctness; indexes can be a follow-up. Browser history and server route fallback need integration tests.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P09-01 | A:Orbit/drama/2020; B:Orbit/comedy/2022; C:Other/drama/2023; q=orbit,genre=drama | A only |
| P09-02 | same fixture; q=orbit,minYear=2021 | B only |
| P09-03 | q="A&B" encoded as A%26B | API sees literal A&B once decoded |
| P09-04 | refresh /movies?q=orbit&genre=drama | same filters and result A |
| P09-05 | open /movies/A directly | detail A loads without prior list navigation |
| P09-06 | open /movies/missing directly | 404 screen |
| P09-07 | five matching ids A,B,C,D,E; page=2,size=2 | C,D; total=5 |
| P09-08 | page=3; change q | page resets to 1 before issuing query |

**Debrief questions:** Which state lives in the URL? In what order are filtering, sorting and pagination applied? Why can a route work after a click but fail on refresh?

### 10. Per-user fixed-window rate limiter

**Candidate question:** Repair cross-user interference and boundary errors in request throttling.

**Exact practice contract:** Original contract: fixed windows [floor(t/W)·W,(floor(t/W)+1)·W); limit L applies per authenticated user. First L requests allowed; later requests return 429 and Retry-After=ceil(window_end−t) seconds. Rejecting a request does not consume another allowance. Updates must be atomic. W=10 seconds,L=2 in fixtures.

**Starter codebase:** Middleware, rateLimitStore.ts or equivalent, auth identity adapter, fake clock and deterministic concurrency tests.

**Progression:** 1 independent keys; 2 exact reset boundary; 3 headers/error behavior; 4 distributed atomic store.

**What can go wrong:** Single global counter; inclusive right endpoint; read-increment-write race; time units mixed; IP used despite a per-user contract.

**Algorithm and verification considerations:** O(1) counter operations; bounded old-window cleanup. Multiple instances require an atomic shared operation, not an in-process lock alone.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P10-01 | U requests at t=0,1,2 | allow,allow,429; Retry-After=8 on third |
| P10-02 | U exhausts window; V requests at t=2 | V allowed |
| P10-03 | U exhausts [0,10); request at t=10 | allowed in new window |
| P10-04 | U exhausts [0,10); request at t=9.2 | 429; Retry-After=1 |
| P10-05 | three simultaneous U requests in empty window | exactly two allowed, one rejected |
| P10-06 | five rejected requests then t=10 request | new-window request allowed |
| P10-07 | W=0 or L=−1 | configuration error |
| P10-08 | same user uses two application instances with shared atomic store | combined allowance remains two |

**Debrief questions:** Is this fixed-window, sliding-window or token-bucket policy? Where is atomicity guaranteed? What happens at t=10?

### 11. Consistent password policy

**Candidate question:** Make registration and password-change validation obey the same documented rules.

**Exact practice contract:** Original practice policy: password must be a string of 8–64 Unicode code points inclusive; no trimming or silent truncation. Missing/non-string→400 INVALID_TYPE; out-of-range→400 INVALID_LENGTH. Both endpoints share validation; a rejected request does not modify credentials. This is an exercise contract, not a recommended production password policy.

**Starter codebase:** Auth routes, shared password validator, schemas/service and endpoint tests; inject a fake credential writer rather than testing cryptography.

**Progression:** 1 find all entry points; 2 centralize existing policy; 3 identical boundaries and errors; 4 explicitly revisit Unicode semantics.

**What can go wrong:** JavaScript UTF-16 length mistaken for code-point length; trimming passwords; frontend-only validation; changing one endpoint only.

**Algorithm and verification considerations:** O(password length); counting code points differs from graphemes and bytes. State the intended measure before changing code.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P11-01 | both endpoints; 7 ASCII characters | 400 INVALID_LENGTH; no credential write |
| P11-02 | both endpoints; 8 ASCII characters | accepted; one credential write |
| P11-03 | both endpoints; 64 ASCII characters | accepted |
| P11-04 | both endpoints; 65 ASCII characters | 400 INVALID_LENGTH |
| P11-05 | password missing or null | 400 INVALID_TYPE |
| P11-06 | password numeric 12345678 | 400 INVALID_TYPE |
| P11-07 | password=8 emoji, each one Unicode code point | accepted as length 8 |
| P11-08 | password has valid leading/trailing spaces | stored exactly as submitted; no trimming |

**Debrief questions:** Why must server validation remain authoritative? What does length mean for emoji? How do you preserve an existing valid credential on failure?

### 12. Delivery accounting and cutoff payments

**Candidate question:** Compute delivery costs precisely and separate total cost from unpaid completed work.

**Exact practice contract:** Original contract: driver rate stored in integer cents/hour; delivery has unique id,driver,start,end, with end>start in integer seconds. Cost=roundHalfUp(rate·duration/3600) once per delivery. Pay-up-to(cutoff) marks unpaid deliveries whose end≤cutoff; repeating a payment is idempotent. Peak counts distinct drivers, not delivery rows, using [start,end) intervals.

**Starter codebase:** drivers.ts, deliveries.ts, costCalculator.ts, paymentLedger.ts, clock.ts; fake timestamps, integer-money fixtures and event-sweep tests.

**Progression:** 1 sub-hour precision; 2 total and unpaid aggregates; 3 cutoff/idempotency; 4 peak distinct active drivers.

**What can go wrong:** Truncating hours; rounding aggregated instead of per delivery; paying partially completed work; double-paying; counting overlapping deliveries from one driver twice.

**Algorithm and verification considerations:** O(n) totals; peak O(n log n) event sweep with per-driver active counts. End events occur before start events at equal timestamps.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P12-01 | rate=1200; duration=1800s | cost=600 cents |
| P12-02 | rate=1200; duration=5400s | cost=1800 cents |
| P12-03 | rate=1; duration=1800s | cost=1 cent by half-up rounding |
| P12-04 | delivery end=10; cutoff=9 then 10 | unpaid at 9; paid at 10 |
| P12-05 | pay cutoff=10 twice | second payment pays zero additional cents |
| P12-06 | unknown driver or end≤start | validation error; ledger unchanged |
| P12-07 | D1 deliveries [0,10),[5,15); D2 [8,12) | peak distinct drivers=2 |
| P12-08 | D1 [0,10); D2 [10,20) | peak=1, not 2 |

**Debrief questions:** Why round once per delivery? What does a payment cutoff mean? How do overlapping deliveries for one driver affect peak count?

### 13. Hand parsing and extensible comparison

**Candidate question:** Parse cards correctly, compare hands using supplied rules, then add a rule variant.

**Exact practice contract:** Original mini-game contract: exactly three distinct physical cards; ranks 2..10,J,Q,K,A mapped 2..14; suits C,D,H,S are identity only. Categories: triple>pair>all-distinct. Triple key=[rank]; pair key=[pair_rank,kicker]; distinct key=ranks descending. Categories then keys compare lexicographically; ties allowed across different suits. No straight or flush in this original rule set. Partial-hand behavior must be added separately.

**Starter codebase:** Python card.py, hand.py, rules.py, game.py; deterministic deck and parser/comparison tests. Do not silently substitute five-card poker.

**Progression:** 1 repair multi-character rank parsing; 2 complete comparison; 3 specify partial hands; 4 alternate rule object and seeded simulation.

**What can go wrong:** Parsing 10H as rank 1; accidental suit tie-break; duplicate physical cards; category ordering inconsistent; importing poker rules not requested.

**Algorithm and verification considerations:** O(h log h) sorting for hand size h; h=3 is constant. Keep identity validation separate from comparison strategy.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P13-01 | parse 10H | rank=10,suit=H |
| P13-02 | parse AS | rank=14,suit=S |
| P13-03 | parse 1H or 10X | validation error |
| P13-04 | hand [2H,2H,3S] | duplicate-card error |
| P13-05 | [2H,2D,2C] vs [AH,AD,KS] | first wins: triple outranks pair |
| P13-06 | [7H,7D,AS] vs [7C,7S,KH] | first wins by kicker A>K |
| P13-07 | [AH,KD,2S] vs [AC,QD,JS] | first wins: [14,13,2]>[14,12,11] |
| P13-08 | [AH,KD,2S] vs [AC,KS,2D] | tie; suits do not break it |

**Debrief questions:** Which rules are given and which did you invent? What is the complete comparison key? Can different physical hands tie?

### 14. Six composable frontend features

**Candidate question:** Add search, status filtering, sorting, pagination, a detail drawer and saved settings to an existing dashboard.

**Exact practice contract:** Original contract: title substring search, exact status filter, sort by title then id, page size=2; apply search→filter→sort→paginate. Filter changes reset page=1. Persist validated view settings but not open drawer state. API responses carry request generation ids; only latest generation may replace rows. Errors and loading are visible.

**Starter codebase:** React Dashboard.tsx, Table.tsx, FilterBar.tsx, DetailDrawer.tsx, viewState.ts, mock API and interaction tests. These six feature choices are original; the account does not list its six.

**Progression:** 1 map components/data flow; 2 implement two features coherently; 3 complete composition and saved state; 4 out-of-order responses.

**What can go wrong:** Six individually working features that conflict; stale requests winning; pagination before filtering; corrupt settings crashing startup; drawer carrying the wrong selected row.

**Algorithm and verification considerations:** O(n log n) client-side reference view. Test interaction composition, not only isolated handlers.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P14-01 | A Alpha/open, B Beta/closed, C Bravo/open; search b,status=open | C only |
| P14-02 | titles Zulu,Alpha,Beta; ascending sort | Alpha,Beta,Zulu |
| P14-03 | ids 1..5 in sorted order; page=2 | ids 3,4 |
| P14-04 | page=3; status filter changes | page=1; filtered first page |
| P14-05 | save status=open and sort=title; reload | same settings restored; drawer closed |
| P14-06 | invalid saved page=−2 | normalize to page 1; page remains usable |
| P14-07 | query old sent before new; old response arrives last | new-query rows remain visible |
| P14-08 | detail A open; API errors on reload | error state shown; no success claim or unrelated detail |

**Debrief questions:** Which feature invalidates pagination? What makes a response stale? How do saved settings evolve when their schema changes?

### 15. LRU, expiration, resize and atomic creation

**Candidate question:** Extend an LRU cache without breaking access order; keep TTL and progressive-cache variants explicit.

**Exact practice contract:** Original contract: capacity≥0; get hit promotes key; miss returns None without changing order; put updates/promotes. TTL is absolute from put, with expiry t≥expires_at; get does not extend it. Expired entries are removed before eviction. resize evicts least-recently-used until compliant. get_or_put serializes same-key creation so one factory runs; errors are not cached.

**Starter codebase:** Python cache.py, clock.py, synchronized wrapper and tests. Public progressive practice covers resize/get_or_put; TTL is our independent extension.

**Progression:** 1 get promotes; 2 eviction; 3 choose TTL or resize variant; 4 concurrent atomic get_or_put.

**What can go wrong:** Insertion order used as recency; expired keys consume capacity; get unexpectedly refreshes TTL; duplicate factories under a race; exception cached as a value.

**Algorithm and verification considerations:** O(1) get/put with hashmap+doubly linked list; expired-entry sweeps may be O(n) unless an expiry index is added.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P15-01 | capacity=2; put A,B; get A; put C | B evicted; order least→most A,C |
| P15-02 | capacity=2; put A,B; get missing; put C | A evicted; miss does not promote anything |
| P15-03 | put A at t=0,ttl=5; get at 4 then 5 | hit at 4; miss at 5 |
| P15-04 | capacity=1; expired A then put B | B retained; A removed |
| P15-05 | put A=1 then A=2 | one entry A=2; A most recent |
| P15-06 | capacity=0; put A then get A | None; cache remains empty |
| P15-07 | order A,B,C; resize to 1 | C only |
| P15-08 | two simultaneous get_or_put(A,factory) | factory called once; both receive same value |

**Debrief questions:** Does get extend TTL? How do resize and expiry interact? Is factory execution at-most-once, and what happens if it fails?

### 16. Verification expiry and one-time use

**Candidate question:** Repair verification codes that remain usable at expiry or after successful consumption.

**Exact practice contract:** Original contract: one active code per user; expires at issued+TTL; valid only now<expires. Correct verification atomically consumes the code; wrong code does not consume it. Resend invalidates old code. Return a uniform verification-failed result for missing,wrong,expired or consumed codes. Inject the clock; do not log codes.

**Starter codebase:** FastAPI verification route/service, token_store.py, fake clock, transaction/in-memory adapter and request tests.

**Progression:** 1 expiry boundary; 2 one-time consumption; 3 resend and wrong-user isolation; 4 concurrent attempts.

**What can go wrong:** Using ≤ expiry; checking then consuming nonatomically; resetting expiry on attempts; mixing user scopes; leaking codes in logs.

**Algorithm and verification considerations:** O(1) keyed lookup; correctness depends on atomic conditional consumption, not the speed of the lookup.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P16-01 | issued=0,TTL=60; correct code at 59 | success; code consumed |
| P16-02 | fresh code; correct code at 60 | verification-failed |
| P16-03 | successful code used again | verification-failed |
| P16-04 | wrong code then correct code before expiry | failure then success |
| P16-05 | U1 code used for U2 | failure; U1 code remains active |
| P16-06 | resend U1 code A→B; verify A then B | failure then success |
| P16-07 | two simultaneous correct verifications | exactly one success |
| P16-08 | unknown user/code | same verification-failed result; no state mutation |

**Debrief questions:** Where is the check-and-consume atomic? Does a wrong attempt consume the token? What policy is deliberately outside this exercise?

### 17. Transactional wallet transfers and retries

**Candidate question:** Fix duplicate debits and partial transfers while preserving total funds.

**Exact practice contract:** Original contract: integer positive cents, distinct existing source/destination; each request has globally unique id. One transaction updates both balances and persists request result. Same id+same payload returns original result; same id+different payload→409. Insufficient funds→422 with no changes. Injected failures roll back all effects; concurrent transfers cannot overdraw.

**Starter codebase:** FastAPI routes/service, SQLite transactional ledger and idempotency table; injected failure points and barrier-controlled concurrency tests.

**Progression:** 1 reproduce partial write; 2 atomic transfer; 3 idempotency and conflict; 4 concurrent debits.

**What can go wrong:** In-memory deduplication lost on restart; idempotency stored before failed transaction; retry checking id but not payload; balance check outside lock/transaction.

**Algorithm and verification considerations:** Indexed request-id and account lookups; transaction isolation/locking determines concurrency safety. Money conservation is necessary but does not establish correct recipient.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P17-01 | A=100,B=0; transfer 30 id=r1 | A=70,B=30; success |
| P17-02 | retry r1 with same payload | same result; balances remain 70,30 |
| P17-03 | reuse r1 with amount=40 | 409; balances unchanged |
| P17-04 | A=20,B=0; transfer 30 | 422; balances remain 20,0 |
| P17-05 | failure injected after debit before credit | rollback; A=100,B=0; no successful r1 recorded |
| P17-06 | A=100; concurrent transfers 70 to B and C | one success, one insufficient-funds; A=30; total=100 |
| P17-07 | amount=0,negative or noninteger | 400; no ledger mutation |
| P17-08 | source=destination or unknown destination | 400 or 404 respectively; no mutation |

**Debrief questions:** What is the transaction boundary? Why store the result with the balances? How do identical retries differ from conflicting reuse?

### 18. Maximum unique-character subset

**Candidate question:** Repair validation, find an optimal compatible subset, then scale to larger lists.

**Exact practice contract:** Original contract: lowercase a–z strings; concatenated selected words contain no repeated character. Empty selection is legal. Select input indices so repeated equal strings are distinct occurrences; each index at most once. Maximize total character count; any optimum accepted. A validator checks legality only, not optimality. Nonalphabetic input is rejected. Empty words contribute zero.

**Starter codebase:** Python max_unique.py/selector.py, subset_utils.py/validator.py; brute-force small-input oracle and larger generated fixtures.

**Progression:** 1 validator correctness; 2 exact baseline solver; 3 bitmask pruning/compatible-state search; 4 measured larger dataset.

**What can go wrong:** Treating a legal suboptimal selection as invalid; ignoring repetition within a word; set membership instead of occurrence accounting; greedy longest-first loses optimality.

**Algorithm and verification considerations:** Bitmasks make compatibility O(1) over a 26-letter alphabet; worst-case subset search remains exponential. Explain pruning without claiming polynomial worst-case exact search.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P18-01 | words [ab,cd,ae]; choose indices [0,1] | valid; length=4; optimum=4 |
| P18-02 | same words; choose [0] | valid but suboptimal length=2 |
| P18-03 | words [aa,b]; solve | choose [1]; optimum=1 |
| P18-04 | words [ab,bc]; choose both | invalid shared b; optimum=2 |
| P18-05 | words [ab,ab]; choose both | invalid; optimum=2 from either occurrence |
| P18-06 | words []; solve | []; optimum=0 |
| P18-07 | words [abc,de,f]; solve | all indices; optimum=6 |
| P18-08 | words [abc,ad,be,cf]; solve | indices [1,2,3]; optimum=6, beating greedy abc |

**Debrief questions:** What is legality versus optimality? Can a word be chosen twice? Why is longest-word-first not generally optimal?

### 19. Toy runway event scheduler

**Candidate question:** Build a scheduling simulation with explicit priority and exclusion rules.

**Exact practice contract:** Original contract: one runway, positive occupancy duration; no preemption after a flight starts. At each free instant pick arrived emergency first, then landing, then takeoff; ties use arrival then id. Arrivals at a finish time are eligible immediately. Cancellation removes only waiting flights; closure [a,b) prohibits any scheduled occupancy overlapping it. This is an interview simulation, not operational aviation guidance.

**Starter codebase:** Python aircraft.py, runway.py, scheduler.py, events.py; fake clock, seeded requests and event-log assertions.

**Progression:** 1 requirements and model; 2 exclusion and priorities; 3 cancellation/closure; 4 second runway with defined eligibility.

**What can go wrong:** Preempting active flights without a requirement; ranking future arrivals ahead of ready work; interval-overlap errors; nondeterministic emergency ties.

**Algorithm and verification considerations:** O(n log n) event/ready queues for the basic model; closure search needs a documented interval strategy.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P19-01 | takeoff T and landing L arrive 0, each duration 2 | L[0,2),T[2,4) |
| P19-02 | emergency X and ordinary landing L arrive 0 | X scheduled first |
| P19-03 | T starts 0 duration5; emergency X arrives1 | T completes5; X starts5; no preemption |
| P19-04 | A finishes5; B arrives5 | B may start5 |
| P19-05 | waiting B cancelled before dispatch | B produces no occupancy |
| P19-06 | closure [5,10); flight arrives4 duration3 | flight starts10; cannot overlap closure |
| P19-07 | closure [5,10); flight arrives2 duration3 | flight occupies [2,5); legal touching boundary |
| P19-08 | two emergency flights arrive0 ids B,A | A before B |

**Debrief questions:** Which policy is an assumption? Can emergencies preempt? What event order applies at a closure boundary?

### 20. Test-contract disagreement and diagnosis

**Candidate question:** Investigate a failed test and determine which side violates the written contract before editing.

**Exact practice contract:** Original parser contract: tokens match [+-]?[0-9]+ after trimming ASCII outer whitespace; output a safe integer in ±(2^53−1). Leading zeros and + are allowed; decimals, empty input, trailing junk and nonstrings are rejected. A deliberately faulty test expects 007 to be rejected. Correct that test with written justification and independent cases; do not broadly weaken validation.

**Starter codebase:** TypeScript parser.ts, schema.ts, contract.md, a small consumer and independently authored test fixtures.

**Progression:** 1 reconcile test and contract; 2 smallest justified correction; 3 independent regressions; 4 changed requirement with explicit migration.

**What can go wrong:** Editing production code to satisfy a wrong assertion; parseInt accepting suffixes; Number accepting empty strings; assuming implementation is the spec despite a contradictory explicit contract.

**Algorithm and verification considerations:** O(token length); bound checking must happen before accepting a result. The exercise evaluates evidence and restraint more than algorithm novelty.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P20-01 | input "007" | 7; faulty rejection expectation must be corrected |
| P20-02 | input "  -12  " | −12 |
| P20-03 | input "+0" | 0 |
| P20-04 | input "12x" | parse error |
| P20-05 | input "1.5" | parse error |
| P20-06 | input empty or whitespace only | parse error |
| P20-07 | input "9007199254740992" | range error |
| P20-08 | input number 12 rather than string | type error |

**Debrief questions:** What proves the test was wrong? Which counterexample would detect an overpermissive parser? How would you handle a newly required no-leading-zero rule?

### 31. Three-card sum-15 strategy

**Candidate question:** Repair selection validation, implement a legal baseline chooser and compare strategies under controlled simulation.

**Exact practice contract:** Original contract: cards have unique physical ids plus amount1..9 and mark; a move contains exactly three distinct table ids with total15. Marks do not affect legality. A chooser returns a legal triple or None when none exists. For our benchmark only, score one point per successful triple, remove those cards, refill from a seeded deck, and report legal moves and score separately. Publisher scoring/refresh details were not obtained.

**Starter codebase:** Python engine.py, pieces.py, strategies.py, seeded deck and validation/simulation tests.

**Progression:** 1 membership/multiplicity bug; 2 baseline combination enumeration; 3 reproducible measurement; 4 improve strategy under a specified score.

**What can go wrong:** Membership as a set while reusing one physical card; inventing a missing card with matching value; optimizing before legality; comparing strategies on different random decks.

**Algorithm and verification considerations:** Enumerating triples O(m³) for m visible cards; value-group lookup can reduce search. Strategy quality requires multiple shared seeds and uncertainty, not one lucky run.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P31-01 | table a=4,b=5,c=6; choose a,b,c | valid total15 |
| P31-02 | same table; choose a,b,missing | invalid membership |
| P31-03 | table a=5,b=5,c=5; choose a,a,b | invalid repeated physical id |
| P31-04 | table a=5,b=5,c=5; choose a,b,c | valid despite equal values |
| P31-05 | table a=1,b=2,c=3; chooser | None; no valid triple |
| P31-06 | table a=4,b=5,c=6; choose a,b | invalid length |
| P31-07 | table a=4,b=5,c=7; choose all | invalid total16 |
| P31-08 | same strategy,deck,seed run twice | same move sequence, legal-move count and score |

**Debrief questions:** Are identity and card value interchangeable? What is the scoring objective? How do you make a fair strategy comparison?

### 32. Friend recommendation validity and ranking

**Candidate question:** Reject invalid recommendations, create a baseline and improve recommendation quality.

**Exact practice contract:** Original contract: undirected known-user graph without self edges; recommendations exclude self,current friends,unknown ids and duplicates. Rank eligible users by mutual-friend count descending, then user id ascending; return at most k, with k=0→[]. The public practice mentions strategy evaluation but its exact quality metric is not available. Our benchmark uses withheld edges and precision@k only when a held-out positive set exists.

**Starter codebase:** Python social_graph.py, recommenders.py, graph fixtures, validator and withheld-edge benchmark.

**Progression:** 1 validator exclusions; 2 baseline recommendations; 3 define offline metric; 4 mutual-friend ranking and larger graphs.

**What can go wrong:** Only checking direct friends; unknown ids accepted; test leakage from withheld edges; popularity accidentally replacing the requested metric.

**Algorithm and verification considerations:** Candidate generation through friends-of-friends costs sum of neighbor degrees; sorting candidates O(c log c). Isolated-user fallback is a specified product choice.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P32-01 | users A,B,C,D; edges A-B,B-C; recommend A,k=2 | [C,D]; mutual counts1,0 |
| P32-02 | same graph; validate [A] for A | invalid self |
| P32-03 | same graph; validate [B] for A | invalid existing friend |
| P32-04 | same graph; validate [C,C] | invalid duplicates |
| P32-05 | same graph; validate [Z] | invalid unknown user |
| P32-06 | users A,B,C; A isolated; k=2 | [B,C]; tie id ascending |
| P32-07 | k=0 | [] |
| P32-08 | users A,B,C; A friends with B and C | []; no eligible candidates |

**Debrief questions:** What does a recommendation score mean? How do you avoid evaluation leakage? What should an isolated user see?

### 33. Straight-line compiler cost and liveness

**Candidate question:** Repair fixture metadata loading, analyze a small program, remove dead assignments and fold constants.

**Exact practice contract:** Original contract: SSA-style arithmetic assignments and aliases; final output res; +,−,*,/ integer operations with per-fixture costs. Our fixture metadata is a JSON header, not a recovered publisher file format. Fold pure constants with division truncating toward zero; reject division by zero. For our liveness model, a new arithmetic temporary is allocated before last-used operands are freed; inputs/constants allocate no temporaries; aliases share storage. Preserve evaluation order of retained instructions.

**Starter codebase:** Python compiler_optimizer.py, optimizer_utils.py, tests/data; parser, dependency graph, cost analyzer and an independent tiny interpreter.

**Progression:** 1 metadata loader; 2 basic cost/liveness; 3 backward dead-code elimination from res; 4 constant propagation/folding. Negative division and memory conventions must be specified by the exercise author.

**What can go wrong:** Hardcoded operator costs; single-digit metadata parsing; counting input variables as temporary memory; dead-code removal by textual names rather than dependencies; ambiguous reuse convention.

**Algorithm and verification considerations:** O(I+dependencies) passes for I instructions; liveness tracks future uses. Optimize correctness and semantic equivalence before comparing cost totals.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P33-01 | cost+=2,*=3; a=x+1; res=a | time2,peak1 |
| P33-02 | same costs; a=x+1; b=a*2; res=b | time5,peak2 under allocate-before-release |
| P33-03 | cost+=2; a=x+1; b=y+1; res=a+b | time6,peak3 |
| P33-04 | a=x+1; unused=y*9; res=a | dead-code elimination removes unused; optimized time2,peak1 |
| P33-05 | a=2+3; res=a*4 | constant result20; optimized time0,peak0 |
| P33-06 | res=−7/2 with constants | constant result−3; time0,peak0 |
| P33-07 | metadata expectedTime=123,expectedMemory=12; costs include *=17 | all multi-digit values preserved; not truncated |
| P33-08 | res=1/0 | compile-time validation error under this original contract |

**Debrief questions:** When is a temporary live? Does res alias allocate storage? What happens to exceptions in dead code under the language contract?

### 34. Dependency impact from changed paths

**Candidate question:** Normalize paths, identify directly affected services and propagate impact to dependents.

**Exact practice contract:** Original contract: absolute case-sensitive POSIX paths; collapse repeated separators and trailing slash except /. Reject . and .. segments rather than silently resolve them. ancestor(A,B) holds when A=B or B begins A+/; / is ancestor of all valid paths. Each service owns watched paths; a changed file affects a watcher of its ancestor. A deleted directory affects watched descendants too. Dependency A→B means A depends on B, so impact propagates from B to A. Cycles terminate.

**Starter codebase:** Python path_utils.py, service_dependency.py, watched-path and dependency graph fixtures; normalization and transitive-impact tests.

**Progression:** 1 path helper; 2 direct file impact; 3 deleted subtrees; 4 reverse dependency closure.

**What can go wrong:** /app matching /apple by string prefix; root lost during trimming; traversing dependency edges in the wrong direction; cycles; treating deletes as ordinary file edits.

**Algorithm and verification considerations:** O(S·W) straightforward path matching plus O(V+E) closure; a path trie is an optional scale extension.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P34-01 | normalize //app///src/ | /app/src |
| P34-02 | normalize //// | / |
| P34-03 | ancestor /app vs /apple/x | false |
| P34-04 | ancestor / vs /app/x | true |
| P34-05 | service B watches /lib; file /lib/a changes; A depends on B | affected {A,B} |
| P34-06 | B watches /lib/sub/a; directory /lib deleted | B affected even though watched path is below deletion |
| P34-07 | A depends B and B depends A; B directly affected | {A,B} once each; termination |
| P34-08 | normalize /app/../secret | validation error |

**Debrief questions:** Why is dependency direction important? How does directory deletion differ from a file edit? Is this path syntax or filesystem resolution?

### 35. Meeting scheduler and atomic reservations

**Candidate question:** Repair overlap checks, find the earliest free slot and prevent concurrent double booking.

**Exact practice contract:** Original contract: intervals [start,end), positive integer duration. Search within [earliest,latestEnd] for a slot fully inside the window. Bookings may overlap in input; search uses their occupied union and leaves input unmodified. Return (start,end) or None. Reservation performs search and insert atomically for a single room. Existing bookings returned sorted by start,end,id.

**Starter codebase:** Python booking_utils.py, scheduler.py, fake clock and in-memory locked store; interval and concurrency tests.

**Progression:** 1 touching-boundary overlap; 2 earliest slot; 3 sorted persistent bookings; 4 atomic reserve.

**What can go wrong:** Closed intervals forbid adjacent meetings; gaps smaller than duration accepted; mutation during sorting; check then insert race; wrong handling of nested bookings.

**Algorithm and verification considerations:** O(n log n) initial sort then O(n) gap scan; O(n) insertion into a list. A lock/transaction protects the full reserve operation.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P35-01 | overlap [0,10),[10,20) | false |
| P35-02 | overlap [0,20),[5,10) | true |
| P35-03 | bookings [0,5),[10,15); duration5,window[0,20] | earliest [5,10) |
| P35-04 | same bookings; duration6,window[0,20] | None |
| P35-05 | no bookings; duration3,window[2,10] | [2,5) |
| P35-06 | unsorted overlapping [5,10),[0,8); duration2,window[0,20] | [10,12); input order unchanged |
| P35-07 | duration0 or end<start | validation error |
| P35-08 | two simultaneous reservations, duration10,window[0,10] | one [0,10) reservation; one None |

**Debrief questions:** Where does half-open semantics matter? What changes for multiple rooms? What part of reserve must be atomic?

### 36. Crawler priority, readiness and retry queue

**Candidate question:** Fix stable priority ordering, then add readiness and bounded retry behavior.

**Exact practice contract:** Original contract: unique job ids; higher integer priority first; FIFO original enqueue sequence breaks equal-priority ties. pop_ready(now) considers only ready_at≤now and leases one job, counting an attempt. A failed attempt requeues at now+5 preserving priority and original sequence; after two total attempts mark dead. Completed/dead jobs cannot be popped again. Empty/no-ready result=None. URLs are opaque; URL deduplication is out of scope.

**Starter codebase:** Python crawl_queue.py, heap_utils.py, fake clock and job store; baseline ordered-list oracle and heap implementation.

**Progression:** 1 tie comparator; 2 push/pop; 3 choose ready jobs despite a delayed higher-priority head; 4 cooldown and retry exhaustion.

**What can go wrong:** Heap head blocks ready lower-priority work; priorities inverted; retry loses FIFO order; leased job still available; unbounded retries.

**Algorithm and verification considerations:** One heap alone cannot efficiently serve priority among ready jobs with arbitrary readiness; split delayed-time and ready-priority heaps. Typical push/pop O(log n).

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P36-01 | A priority1 seq0,B priority3 seq1 both ready | B then A |
| P36-02 | A priority3 seq0,B priority3 seq1 | A then B |
| P36-03 | A priority9 ready_at10,B priority1 ready_at0; now0 | B; delayed A does not block it |
| P36-04 | A ready_at5; pop at4 then5 | None then A |
| P36-05 | A fails first attempt at0; pop at4 then5 | None then A on attempt2 |
| P36-06 | A fails second attempt at5; pop later | A dead; None |
| P36-07 | push duplicate active id A | validation error; one A remains |
| P36-08 | lease A then second pop before completion | A not returned again |

**Debrief questions:** How can a delayed high-priority job hide ready work? Which order survives retries? What happens if a worker dies after leasing?

### 37. Expense rules and grouped decisions

**Candidate question:** Repair numeric amount comparison, then compose per-expense and per-trip rules.

**Exact practice contract:** Original contract: amounts are nonnegative decimal strings with at most two fractional digits, parsed to integer cents without float comparisons. Expense exceeds a threshold only when amount>threshold, so equality passes. Trips sum their expense amounts; reject duplicate expense ids and malformed currency. AND/OR rule composition uses explicit booleans; return violations in stable (trip,id,rule) order. No currency conversion in this exercise.

**Starter codebase:** Python expense_engine.py, expense_rules.py, schema/decimal parser and fixtures containing per-item and per-trip rules.

**Progression:** 1 numeric versus lexical comparison; 2 per-expense rules; 3 aggregate/composite checks; 4 deterministic large-input evaluation.

**What can go wrong:** Lexicographic ordering; binary-float boundary error; grouping globally instead of by trip; rounding each amount differently; duplicate charges in sums.

**Algorithm and verification considerations:** O(n·r) direct rule checks and O(n) grouping; precompile rules only when workload warrants it.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P37-01 | amount="100.00",threshold="20.00" | violation; 10000>2000 cents |
| P37-02 | amount="9.00",threshold="100.00" | no violation |
| P37-03 | amount="20.00",threshold="20.00" | no violation |
| P37-04 | trip T amounts10.10 and0.20,trip limit10.30 | no violation; sum=1030 cents exactly |
| P37-05 | same trip; limit10.29 | trip violation; sum exceeds by1 cent |
| P37-06 | T1=7,T2=7; each trip limit10 | no violation; do not combine trips |
| P37-07 | amount="1.001" or "NaN" | validation error |
| P37-08 | rule (amount>10 AND category=meal); expense12,category=travel | no violation; AND requires both |

**Debrief questions:** Why integer cents? Is equality a violation? How are individual and trip rules combined and explained?

### 38. Contained-string search and progressive scaling

**Candidate question:** Find a string containing another list entry, then add shortest-container and all-pairs variants.

**Exact practice contract:** Original contract: nonempty case-sensitive strings; containment must use different list positions. Equal strings at different indices count. Baseline returns any valid container index or None; shortest variant minimizes length then index. All-pairs variant returns sorted directed (container_index,contained_index) pairs; overlapping substring occurrences still produce one pair. Do not confuse containing one entry with containing every entry.

**Starter codebase:** Python substring_finder.py, benchmark.py, oracle fixtures and generated large lists; a slow pairwise baseline is supplied.

**Progression:** 1 basic correctness; 2 shortest valid container; 3 larger inputs; 4 all valid directed pairs.

**What can go wrong:** Self-containment incorrectly accepted; duplicates removed before evaluation; case normalization changes semantics; substring occurrence count confused with pair count.

**Algorithm and verification considerations:** Baseline O(n²·L) with implementation-dependent substring-search cost. Multi-pattern matching can improve work, but output may itself contain Θ(n²) pairs.

**Concrete practice scenarios** (test-design fixtures, not executable implementations):

| ID | Input/action sequence | Expected observation |
|---|---|---|
| P38-01 | strings [catalog,log] | container index0; pair (0,1) |
| P38-02 | strings [sun,moon] | None; pairs[] |
| P38-03 | strings [solo] | None; self-match excluded |
| P38-04 | strings [echo,echo] | either container; all pairs[(0,1),(1,0)] |
| P38-05 | strings [ABC,bc] | None; case-sensitive |
| P38-06 | strings [longabc,abc,xabc]; shortest variant | index2 xabc, length4 |
| P38-07 | strings [ababa,aba,ba]; all-pairs | [(0,1),(0,2),(1,2)] |
| P38-08 | strings [abc,xabc,yabc]; shortest variant | index1 xabc wins equal-length tie |

**Debrief questions:** Can two identical strings count? What is the output-size lower bound for all pairs? Does a faster algorithm preserve shortest-container ties?

## Existing PromptCode questions 21–30: deeper interpretation

The linked [local appendix](/Users/shrutwik/Desktop/PromptCode/docs/ai-assisted-interview-local-tests.md) contains every visible assertion and trusted expected result. This section explains what those cases are targeting. These are local exercise contracts, not external interview attributions.

### 21. tenant-document-acl

**What is being asked:** Authorization must constrain both read and mutation lookups, not merely list queries. The error deliberately conceals cross-tenant existence.

**Important verification distinction:** Assert the rejected response and all stored fields; test both tenant directions and invalid credentials. A filtered response alone cannot prove isolation.

**Codebase:** [candidate instructions](/Users/shrutwik/Desktop/PromptCode/challenges/tenant-document-acl/README.md); 7 visible named test definitions; 9 trusted probes.

**Registered manual gap:** None registered beyond the behavioral inventory; no claim of exhaustive correctness.

### 22. webhook-delivery-retry

**What is being asked:** Separate retry attempts from per-delivery side effects. Charge is once per delivery processing, including eventual failure; it is not charged only on HTTP success.

**Important verification distinction:** Check attempt count, total charges, maximum in-flight posts, input-order results and empty batches. Idempotency scope beyond a single process is a follow-up, not automatically covered.

**Codebase:** [candidate instructions](/Users/shrutwik/Desktop/PromptCode/challenges/webhook-delivery-retry/README.md); 5 visible named test definitions; 6 trusted probes.

**Registered manual gap:** None registered beyond the behavioral inventory; no claim of exhaustive correctness.

### 23. invoice-status-transition

**What is being asked:** The full directed graph is draft→sent/void, sent→paid/void, paid→void, void→nothing. Self transitions are illegal in this snapshot.

**Important verification distinction:** The trusted transition matrix checks every pair and API status/state behavior. Illegal and malformed requests preserve state and amount; missing record and missing status are distinct.

**Codebase:** [candidate instructions](/Users/shrutwik/Desktop/PromptCode/challenges/invoice-status-transition/README.md); 8 visible named test definitions; 6 trusted probes.

**Registered manual gap:** None registered beyond the behavioral inventory; no claim of exhaustive correctness.

### 24. subscription-proration-boundary

**What is being asked:** Period ownership is half-open [start,end); before-start cancellation receives no credit. Normalize offset-aware instants, not display strings.

**Important verification distinction:** Protect the 1600-cent January midpoint credit, adjacent period ownership, offsets and microsecond boundaries; avoid making the entire period non-billable to fix its endpoint.

**Codebase:** [candidate instructions](/Users/shrutwik/Desktop/PromptCode/challenges/subscription-proration-boundary/README.md); 7 visible named test definitions; 7 trusted probes.

**Registered manual gap:** None registered beyond the behavioral inventory; no claim of exhaustive correctness.

### 25. shipment-csv-merge

**What is being asked:** Identity is event_id, not shipment/status. Global timestamp ordering and tied-id determinism coexist with separate shipment totals.

**Important verification distinction:** Each merge replaces the summary snapshot rather than accumulating stale global state. Test duplicate ids across files, distinct same-status events, negative quantities and empty reset.

**Codebase:** [candidate instructions](/Users/shrutwik/Desktop/PromptCode/challenges/shipment-csv-merge/README.md); 6 visible named test definitions; 6 trusted probes.

**Registered manual gap:** None registered beyond the behavioral inventory; no claim of exhaustive correctness.

### 26. notification-feed-stale

**What is being asked:** Concurrent mark operations must merge into current state after awaited work. Badge is derived from or synchronized with the current read flags.

**Important verification distinction:** Repeated same-id and different-id actions both matter. Failure must preserve state. Store probes do not prove the rendered React badge; that is explicit manual review.

**Codebase:** [candidate instructions](/Users/shrutwik/Desktop/PromptCode/challenges/notification-feed-stale/README.md); 5 visible named test definitions; 6 trusted probes.

**Registered manual gap:** React rendered badge matches store

### 27. order-hold-reason

**What is being asked:** Persist reason through request schema, model, service and response. Preserve customer and total; legacy records expose null.

**Important verification distinction:** Test Unicode overwrite, omitted reason, later GET, isolation from other orders and repeated release. A response echo without persistence is insufficient.

**Codebase:** [candidate instructions](/Users/shrutwik/Desktop/PromptCode/challenges/order-hold-reason/README.md); 6 visible named test definitions; 6 trusted probes.

**Registered manual gap:** None registered beyond the behavioral inventory; no claim of exhaustive correctness.

### 28. workspace-label-propagation

**What is being asked:** A label list is validated against the ticket workspace before any update; rejected mixed lists preserve the old valid list.

**Important verification distinction:** PUT→GET checks persistence, clear-list checks semantics, list endpoint checks workspace isolation, rendered UI checks selected ids. Server success does not prove the UI.

**Codebase:** [candidate instructions](/Users/shrutwik/Desktop/PromptCode/challenges/workspace-label-propagation/README.md); 7 visible named test definitions; 5 trusted probes.

**Registered manual gap:** React screen displays persisted labels

### 29. catalog-suggest-latency

**What is being asked:** Preserve score: +10 per query-token membership and +5 category equality; score descending, popularity descending, id ascending. Normalize the query and do not mutate products.

**Important verification distinction:** Visible performance uses 3 warmups and 7 samples on 10,000 products, median under 200ms, with scan constraints. Trusted probes check ranking, not calibrated latency or trustworthy instrumentation.

**Codebase:** [candidate instructions](/Users/shrutwik/Desktop/PromptCode/challenges/catalog-suggest-latency/README.md); 7 visible named test definitions; 5 trusted probes.

**Registered manual gap:** 200ms latency under calibrated load; scan instrumentation cannot be self-attested

### 30. pricing-rule-extract

**What is being asked:** Extract the existing loop so quote delegates to applyRules. Current starter applyRules delegates to quote: identical outputs alone cannot establish the required refactor direction.

**Important verification distinction:** Preserve percent_off→amount_off→surcharge_percent ordering, per-operation half-up rounding, applied-code order and final floor-at-zero. Inspect source delegation separately from golden output tests.

**Codebase:** [candidate instructions](/Users/shrutwik/Desktop/PromptCode/challenges/pricing-rule-extract/README.md); 7 visible named test definitions; 6 trusted probes.

**Registered manual gap:** quote delegates to extracted applyRules; source review

## Test coverage that makes these questions meaningful

For each exercise, distinguish a contract assertion from an implementation detail. Preserve a slow independent oracle where possible; a test copied from the candidate algorithm can repeat its bug. Boundary tests should check just below, exactly at and just above the threshold. Mutation tests should check the untouched stored state as well as the error response. Concurrency tests should force a relevant interleaving with barriers or deferred promises rather than rely on arbitrary sleeps.

Useful cross-cutting checks: round-trip invariants, tenant/user isolation, retry idempotency, input immutability, exact monetary arithmetic, deterministic ties, explicit empty/unreachable output, clock-offset equivalence and output-order stability. For graph tasks, add node renaming and unreachable-component properties. For performance tasks, check reference-output parity before comparing timing. For simulations, use shared seeds and independent legality checks; never replace hard correctness with an average quality score.

The eight cases per original specification are a concrete starting suite, not exhaustive coverage. Additional generated property tests, interaction tests and changed requirements should be calibrated to the exercise contract. In particular, the canvas and dashboard scenarios need an actual browser/component harness; concurrent wallet/reservation scenarios need a transaction-capable implementation. These fixtures are designs until implemented.

## Assessment and codebase packaging

A proposed assessment should record tool permission, time limit, stack/setup, candidate-visible contract, exact allowed edit scope, fixture data, reproducible commands and separate interviewer notes. Supply working surrounding behavior and a focused defect or incomplete module; setup failures should not dominate the coding task. Keep interviewer expected outputs and repair implementations outside candidate delivery.

A practical original rubric can score: contract/model clarity, root-cause or feature correctness, regression protection, verification quality, explanation of changed code and response to a new requirement. Choose weights deliberately after mock runs; these sources do not publish a universal rubric. Inspect whether the candidate catches unsupported AI assumptions, can explain invariants, and selects tests that would reject a plausible wrong fix. AI prompt count and a green advisory test report are not sufficient evidence.

Suggested baseline runtime for a mock is 45–60 minutes for a focused bug and 60–90 minutes for a staged build. These are editorial calibration starting points, not verified employer durations except where an individual report explicitly gives its own duration. Start with a runnable scaffold, initial failing demonstration, independent small oracle and deterministic clock/deck. Gate later stages on a stable baseline rather than exposing every extension at once.

## Completeness and verification ledger

- 38 exercises: 28 original detailed specifications and 10 local challenges.
- 224 uniquely identified original practice scenarios.
- 13 public practice pages with 40 visible first-stage identifiers; assertion bodies and later-stage tests not obtained.
- 12 exact local visible test files plus one fixture file; 65 named definitions, not runtime executions.
- 62 trusted probes, including full observation code, expected JSON, weights and inventory digests.
- Four local challenge families register additional manual review requirements.
- Source hashes preserve the local snapshot; subsequent code changes can invalidate the snapshot.
- Documentation counts, expected-output export, 52 local link occurrences, balanced Markdown fences and source hashes were checked across the reports. Eleven representative graph, subset, substring and exact-money examples were independently checked. Candidate application tests and Docker grading were not run; this research pass certifies inventory extraction and those examples, not working repairs.

Remaining unavailable information: employer-private code, complete unpublished prompts, hidden assertions, interviewer score sheets, company-wide frequency and uniform tool permissions. The detailed original contracts resolve those unknowns for practice use without claiming discovery.
