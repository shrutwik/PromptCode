# CLAUDE.md — Low-Token Brownfield Mode

> This repo already exists.
> Goal: make the smallest correct change with the fewest tokens.

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
4. patch minimally
5. verify cheaply
6. stop