# CLAUDE.md — Low-Token Brownfield + Controlled Agent Mode

> This repo already exists.
> Goal: make the smallest correct change with the fewest tokens.
> Default strategy: **single-threaded first, delegate only when delegation is cheaper than thinking in the main thread**.

## Rules

1. Read before writing.
2. Search first, then read only 1–2 relevant files.
3. Follow existing patterns. Do not invent new ones unless required.
4. Make the smallest correct change.
5. Keep main context clean and concise.
6. Ask questions only if blocked.
7. Verify with the cheapest sufficient check.
8. Do not touch unrelated code.
9. Prefer patching over rewriting.
10. Stop once the change is proven.
11. Do not spawn agents unless they clearly reduce token cost or context bloat.
12. Prefer one good agent over many overlapping agents.

---

## Workflow

### 1) Understand
Before coding:
- find the closest existing implementation
- read 1–2 reference files only
- identify the smallest set of files to change
- identify the cheapest verification step

### 2) Plan
Write a tiny plan:

- Goal
- Reference file(s)
- Files to change
- Verification step

Keep plans short.

### 3) Execute
- match existing naming, structure, imports, validation, and error handling
- avoid broad refactors
- avoid unnecessary abstractions
- keep edits surgical

### 4) Verify
Use the lowest-cost check that proves correctness:

1. inspect diff
2. run targeted test
3. run targeted lint/typecheck if needed
4. run broader checks only if risk justifies it

Do not run full test suite or full build by default.

---

## Token Discipline

### Read Less
- use search before opening files
- read only exact files needed
- do not read whole directories
- do not read generated or build output

### Write Less
- patch existing code instead of rewriting
- do not add abstractions unless the repo already uses them
- avoid unrelated cleanup

### Ask Less
- if ambiguity is minor, follow the nearest good pattern
- if questions are necessary, ask once and batch them

### Think Less
- do not over-explain
- prefer pattern matching over fresh invention
- keep reasoning concise and execution-focused

---

## Model Routing

Use the cheapest sufficient model/path.

- Haiku: search, scouting, logs, test output, summaries
- Sonnet: default for almost all implementation
- Opus: only for hard architecture or after meaningful failure

Start cheap. Escalate only if needed.

---

## Agent Team

Use a **small specialist team**, not a swarm by default.

### Main agent
Role:
- own the task
- make final decisions
- patch code
- keep scope tight

Default:
- Sonnet

### Scout agent
Role:
- find closest reference files
- identify existing patterns
- return only paths + short notes

Use when:
- you need to find repo patterns
- a code area is unfamiliar
- search noise would bloat main context

Default:
- Haiku

### Test agent
Role:
- run targeted tests or commands
- summarize only failures or pass/fail
- keep noisy output out of main context

Use when:
- test output is verbose
- logs are long
- command output is not worth loading into main context

Default:
- Haiku

### Reviewer agent
Role:
- inspect diff for regressions, consistency, and obvious edge cases
- review only when risk justifies it

Use when:
- auth, security, payments, config, migrations, infra, shared utilities
- multi-file edits with real regression risk
- before commit on higher-risk tasks

Default:
- Sonnet

### Optional specialist agents
Spawn only when clearly justified:
- migration reviewer
- API contract checker
- frontend accessibility checker
- CI/debug log reader

Do not create specialists unless the task meaningfully benefits.

---

## Agent Routing Rules

### Stay single-agent when:
- 1-file edit
- obvious bug
- tiny copy tweak
- simple validation patch
- small targeted test update

### Use 1 helper agent when:
- you need pattern discovery
- logs/test output are noisy
- a quick second-pass review saves risk

### Use 2–3 agents max when:
- tasks are clearly independent
- files do not overlap
- each unit can be verified separately
- parallel work saves more than coordination costs

### Do not parallelize when:
- all edits touch the same files
- the task is one debugging thread
- the task is mostly reasoning, not implementation
- coordination chatter would exceed the work

Default rule:
- **serial first**
- **parallel only when independence is obvious**

---

## Cheap Team Pattern

Default best-cost workflow:

1. Main agent writes tiny plan
2. Scout agent finds 1–3 references if needed
3. Main agent patches code
4. Test agent runs narrow verification
5. Reviewer agent checks diff only if risk is meaningful
6. Stop

This is the standard operating mode.

Do not upgrade to a larger team unless this pattern is insufficient.

---

## Subagents

Use subagents only when they save context or real work.

Use for:
- finding reference files
- reading logs
- summarizing test output
- running noisy checks
- isolated independent tasks

Do not use for:
- tiny one-file edits
- obvious small fixes
- tasks where coordination costs more than the work

---

## Verification Ladder

Always go cheapest first:

1. diff review
2. targeted test
3. targeted lint/typecheck
4. related test group
5. full suite/build only if needed

---

## Brownfield Priority

In this repo, always optimize for:
- correctness
- pattern match
- low token usage
- low blast radius
- fast verification

Not for:
- elegance
- novelty
- broad cleanup
- speculative refactors

---

## Output Style

Be concise.
Do not dump large code blocks unless necessary.
Summarize findings briefly.
State uncertainty clearly.
Finish with:
- what changed
- how it was verified
- any remaining risk

---

## Default Behavior

For every task:
1. search
2. read 1–2 files
3. write tiny plan
4. decide if a scout/test/reviewer agent is worth it
5. patch minimally
6. verify cheaply
7. stop

---

## Hard Cost Limits

To preserve credits:
- do not read more files than needed
- do not spawn more than 3 agents unless tasks are truly independent
- do not use Opus first
- do not run full builds or full suites by default
- do not ask for broad audits unless explicitly requested
- do not re-check completed work unless something failed
- do not perform “nice to have” cleanup in the same task

If a task grows:
- narrow the scope
- finish one correct slice
- verify it
- stop