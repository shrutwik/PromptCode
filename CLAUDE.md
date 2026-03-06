# CLAUDE.md — Brownfield Fast Ship + Credit Preservation

> **This repository already exists.** You are extending it, not reinventing it.
> Your job: understand what exists → plan the smallest correct change → execute → verify → commit.
> Optimize for **shipping useful work with the fewest possible tokens and credits**.
>
> Default mindset: **read less, change less, ask less, verify enough, move on**.

---

## Cardinal Rules

1. **READ BEFORE YOU WRITE** — Search for existing patterns before creating anything new. Most work is a variation of something already in the repo.
2. **SMALLEST CORRECT CHANGE** — Prefer the narrowest implementation that satisfies the request. Do not expand scope unless required.
3. **PLAN EVERY CHANGE** — Write a short plan before coding. A 5-line plan is cheaper than a 50-message recovery.
4. **MATCH EXISTING PATTERNS** — Follow the nearest good implementation. Do not invent a new style if the repo already has one.
5. **PROTECT CREDITS** — Use the cheapest sufficient model/tool path first. Escalate only when the task proves it needs more.
6. **KEEP MAIN CONTEXT CLEAN** — The main thread coordinates. Reading, logs, test noise, and wide exploration should be delegated or kept minimal.
7. **VERIFY BEFORE DECLARING DONE** — Run the smallest meaningful verification that proves the change works.
8. **NEVER MAKE THE SAME MISTAKE TWICE** — Check `MEMORY.md` before starting; log lessons after failures.
9. **ONE MESSAGE, COMPLETE RESULT** — Do not force unnecessary back-and-forth. Batch questions if truly needed.

---

## Project

<!-- Fill these in for best results -->
- **Name**: [Your Project]
- **Stack**: [e.g. Next.js / Prisma / PostgreSQL / Tailwind]
- **Entry points**: [e.g. `src/app/`, `src/components/`, `src/lib/`]
- **Key patterns**:
  - API routes: [e.g. `src/app/api/{resource}/route.ts`]
  - Components: [e.g. `src/features/{name}/`]
  - State: [e.g. Zustand / Redux / React Query]
  - Tests: [e.g. Vitest / Playwright / Jest]
- **Commands**:
  ```bash
  npm run dev
  npm run build
  npm run test
  npm run lint
  npm run typecheck
  ```
- **Do NOT touch**: [paths or systems to avoid]
- **Active branches**: [e.g. `main`, `staging`]
- **Canonical references**:
  - API routes: [best example file]
  - Forms/components: [best example file]
  - Store/state: [best example file]
  - Tests: [best example file]

---

## 1. Operating Goal

The goal is not maximum output per response.
The goal is **maximum shipped value per credit**.

That means:
- reuse existing patterns
- avoid reading unnecessary files
- avoid large rewrites
- avoid deep reasoning unless needed
- avoid expensive models unless needed
- avoid parallel agents unless the work is clearly divisible

Do not optimize for elegance at the expense of cost.
Optimize for **fit, correctness, and low-token execution**.

---

## 2. Core Workflow

Every task follows this loop.

### Step 1: Understand

Before planning or coding:
1. Search for existing implementations of the same or closest pattern.
2. Read **1–2 reference files**, not whole directories.
3. Check `MEMORY.md` for relevant lessons.
4. Identify the smallest file set likely to change.
5. Note the verification path before writing code.

Preferred search order:
1. `rg` / `grep`
2. `Glob` / file listing
3. Read exact files

Never begin by opening broad directories or long files without a reason.

### Step 2: Plan

Write a short plan for every task.

For tiny tasks, keep it in chat:

```markdown
## Task
Goal: Fix X with the smallest safe change.
Reference: `path/to/reference.ts`
Changes:
1. `file-a.ts` — update logic
2. `file-b.test.ts` — add/adjust test
Verify: `npm run test -- file-b.test.ts`
```

For anything touching 3+ files or carrying risk, write `plan.md` in `.planning/`.

A plan must include:
- goal
- reference file(s)
- files to change
- edge cases
- verification step

### Step 3: Execute

- follow existing patterns exactly
- make the smallest viable edit
- avoid opportunistic refactors
- keep one logical change per commit
- if the current approach starts drifting, stop and narrow scope

### Step 4: Verify

Run the cheapest verification that proves correctness:
1. targeted test
2. targeted typecheck/lint if relevant
3. build only when necessary
4. manual spot-check only when required

Do **not** run the full suite by default.
Do **not** run the production build by default.
Escalate verification only if risk justifies it.

---

## 3. Credit Preservation Rules

These rules are mandatory.

### Read Less
- Read only the files needed for the current task.
- Read one strong reference file instead of five mediocre ones.
- Prefer searching for symbols/patterns over opening full files.
- Never read generated, vendor, or build output.

### Write Less
- Patch existing code instead of rewriting unless rewrite is clearly cheaper and safer.
- Do not add abstractions unless the repo already uses them for the same case.
- Avoid cosmetic churn in unrelated lines.

### Ask Less
- Ask questions only if the answer materially changes implementation.
- If multiple details are unclear, batch them into one message.
- If ambiguity is minor, follow the closest established pattern.

### Think Less, But Enough
- Do not use long-form reasoning for routine repo work.
- Prefer pattern matching over fresh invention.
- Only escalate into deeper architecture thinking when the change truly spans multiple systems.

### Verify Cheaply
- Start with the narrowest test or command.
- Only run broader checks if the narrow check fails or the blast radius is wider.

---

## 4. Model Routing

Always use the **cheapest sufficient path**.

| Task | Model | Default Use |
|------|-------|-------------|
| File search, pattern scouting, log reading, test output parsing | `haiku` | First choice |
| Routine implementation, small bug fixes, normal feature work | `sonnet` | Default |
| Complex architecture, multi-system refactor, repeated Sonnet failure | `opus` | Rare escalation |

### Escalation Policy

Start at the lowest level that can realistically succeed.

Use **Haiku** for:
- searching patterns
- summarizing logs
- reading large outputs
- locating reference files
- running and summarizing tests

Use **Sonnet** for:
- implementing most changes
- debugging moderate issues
- multi-file edits with clear patterns
- writing or adjusting tests

Use **Opus** only when:
- Sonnet has already failed meaningfully
- architecture tradeoffs are nontrivial
- the task spans many subsystems and pattern matching is insufficient

Never start in Opus for routine brownfield work.

### Suggested settings

```json
{
  "model": "sonnet",
  "env": {
    "MAX_THINKING_TOKENS": "8000",
    "CLAUDE_AUTOCOMPACT_PCT_OVERRIDE": "50",
    "CLAUDE_CODE_SUBAGENT_MODEL": "haiku"
  }
}
```

Lower `MAX_THINKING_TOKENS` further if you consistently do narrow repo tasks.

---

## 5. Subagent Strategy

Subagents are useful when they **reduce main-context bloat** or enable real parallelism.
They are wasteful when used on tiny tasks.

### Spawn subagents for:
- scouting large code areas
- reading logs or long test output
- running targeted tests
- implementing independent tasks with clear boundaries
- reviewing a diff after implementation

### Do not spawn subagents for:
- a one-file edit
- a tiny rename
- a trivial bug fix with an obvious patch
- tasks where coordination overhead exceeds work

### Default agents

#### `.claude/agents/scout.md`
```yaml
---
name: scout
description: Finds existing repo patterns and the closest reference implementation
tools: Read, Glob, Grep
model: haiku
---
You are a codebase scout.
1. Find the closest existing implementation.
2. Return 1-3 reference files.
3. Note naming, folder, import, and error-handling conventions.
4. Keep it concise. Do not dump file contents.
```

#### `.claude/agents/executor.md`
```yaml
---
name: executor
description: Implements a planned change with fresh context
tools: Read, Write, Edit, Bash, Glob, Grep
model: sonnet
---
Read the plan and the reference files.
Implement the smallest correct change.
Match existing patterns exactly.
Run the listed verification.
Keep output concise.
```

#### `.claude/agents/reviewer.md`
```yaml
---
name: reviewer
description: Reviews a diff for correctness, consistency, and risk
tools: Read, Glob, Grep
model: sonnet
---
Review the diff.
Check pattern match, regressions, edge cases, and security basics.
Return only issues by severity or LGTM.
```

#### `.claude/agents/test-runner.md`
```yaml
---
name: test-runner
description: Runs the narrowest requested verification and summarizes results
tools: Read, Bash, Glob
model: haiku
---
Run the requested command.
Return only pass/fail, failing file:line, and the shortest useful summary.
```

---

## 6. Pattern Matching First

The cheapest successful solution usually comes from copying the repo’s existing shape.

### Before creating anything new

```bash
# find similar handlers or functions
rg "createUser|createPost|updateSettings|route.ts" src

# find feature folder patterns
find src -maxdepth 3 -type d | head -100

# find test patterns
find src -name "*.test.*" -o -name "*.spec.*"
```

### Prompting by reference

Bad:
> Build a full new preferences endpoint with validation and proper typing.

Good:
> Add `src/app/api/preferences/route.ts` following `src/app/api/profile/route.ts`. Same auth check, same validation style, same error shape.

Reference-driven prompting is cheaper and produces code that fits.

### When patterns conflict

Choose one canonical pattern and document it in the Project section.
Avoid mixing old and new approaches in the same feature.

---

## 7. Existing Repo Tool Routing

Use tools only when the overhead is worth it.

### Claude Code only
Use for:
- 1–3 file edits
- small bug fixes
- routine feature additions following clear patterns
- targeted tests and simple verification

### GSD Quick
Use for:
- ad hoc tasks that still benefit from a tracked plan and atomic summary
- medium tasks where you want structure without full phase ceremony

Use command pattern:
- `/gsd:quick` for scoped work

### GSD Full Workflow
Use only for:
- larger multi-step features
- work that benefits from formal requirements/phase planning
- changes likely to span enough time that context rot matters

Use only when the overhead will be repaid by reduced confusion.
Not for small fixes.

### Ruflo
Use only for:
- clearly parallelizable tasks
- repeated work across multiple independent files/modules
- routing commodity work to cheaper agents
- situations where memory/routing/swarm behavior materially helps

Do **not** use Ruflo swarm just because it is available.
Swarm overhead can cost more than it saves.

### Vibe Kanban
Use for:
- workspace isolation
- review-heavy work
- branch-per-task workflows
- cases where visual issue tracking and diff review save real time

Do not use it as the default path for small solo changes.

---

## 8. Swarm Trigger Thresholds

Parallel agents should only run when tasks are both **independent** and **nontrivial**.

Use swarm/parallel execution when most of these are true:
- 3+ independent units of work
- each unit has a clear file boundary
- low merge conflict risk
- one task does not require constant output from another
- each unit can be verified separately

Do **not** parallelize when:
- all tasks touch the same files
- the task is mostly debugging one issue
- the work is under ~30 minutes for a single agent
- coordination chatter will exceed implementation effort

Default rule:
- **serial first, parallel second**
- parallelize only where independence is obvious

---

## 9. Quick Mode

For small, well-scoped changes:

Workflow:
1. scout
2. tiny plan
3. patch
4. verify narrowly
5. commit

Example:

```text
Task: Fix login button bug on mobile Safari
Scout: Find button component and similar touch handling
Plan: patch handler/style in one component and test the affected flow
Verify: targeted test or local interaction check
Commit: fix(auth): resolve mobile Safari login tap issue
```

No phase system.
No heavy research.
No swarm.
Just ship.

---

## 10. Verification Ladder

Always climb from cheapest to most expensive.

1. read diff for obvious mistakes
2. targeted test
3. targeted lint/typecheck on changed area
4. related test group
5. full test suite
6. full production build

Default stopping point: the lowest level that gives confidence proportional to risk.

Examples:
- one logic fix in a tested module → targeted test is enough
- shared type change across many files → targeted typecheck + related tests
- routing/build config change → broader verification may be required

---

## 11. MEMORY.md Rules

### Check before starting
Read `MEMORY.md` for lessons in the same area.

### Write after any of these
- you introduced a bug
- an approach failed and had to be redone
- the user corrected an assumption
- a repo convention surprised you
- a command/tool path failed

### Format

```markdown
## Lesson: [Short title]
- What happened: [1-2 sentences]
- Root cause: [why]
- Fix: [correct approach]
- Area: [auth / api / testing / build / db / repo]
```

### Promotion rule
If the same lesson appears 3+ times, convert it into a permanent rule in this file.

---

## 12. Context Hygiene

### Never read
```text
node_modules/  .next/  dist/  build/  coverage/  .git/  *.lock  *.map
```

### Keep context lean
- clear between unrelated tasks
- compact after finishing a feature
- pass file paths, not pasted contents
- delegate logs and test output to Haiku when useful
- do not keep stale architectural discussion alive once implementation starts

### MCP hygiene
- disable unused MCP servers
- prefer local CLI tools when simpler
- do not add extra tooling to the loop unless it saves more than it costs

---

## 13. Git Workflow

### Atomic commits
One logical change per commit.

Examples:
```text
feat(settings): add user preferences endpoint
fix(auth): handle expired session redirect
test(api): add coverage for invalid settings payload
refactor(store): simplify session selector
```

### Revert over patching drift
If the implementation starts to sprawl or gets conceptually wrong:
- revert
- narrow scope
- restart from the clean smallest goal

That is usually cheaper than incremental salvage.

---

## 14. Hooks

Free guardrails are good because they cost no tokens.

Example:

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Write|Edit",
        "command": "npm run lint:fix -- --quiet $CLAUDE_FILE_PATH 2>/dev/null || true"
      }
    ]
  }
}
```

Prefer local automated formatting/linting over spending credits on style cleanup.

---

## 15. Anti-Patterns

| Do Not | Do Instead |
|--------|------------|
| Read whole folders to understand one change | Search, then read 1-2 exact files |
| Use Opus by default | Start with Haiku/Sonnet |
| Spawn agents on tiny tasks | Keep simple tasks single-threaded |
| Run full test suite immediately | Start with targeted verification |
| Rewrite when a patch works | Patch existing code |
| Ask multiple rounds of questions | Batch necessary questions once |
| Invent new conventions | Match existing repo patterns |
| Mix unrelated cleanup into a feature | Keep changes surgical |
| Keep stale context across unrelated work | Clear/compact aggressively |
| Overuse GSD/Ruflo/Vibe overhead | Use them only when payoff is clear |

---

## 16. Session Workflow

### Starting work
1. Read this file.
2. Check `MEMORY.md`.
3. Search for the closest existing pattern.
4. Read 1-2 reference files.
5. Write a minimal plan.
6. Implement the smallest correct change.
7. Verify using the ladder.
8. Commit atomically.

### Resuming work
1. Read this file.
2. Check `git status` and recent commits.
3. Check `MEMORY.md`.
4. Resume from the smallest pending unit.

### Ending work
1. Verify current changes.
2. Commit or revert partial drift.
3. Log lessons to `MEMORY.md`.
4. Leave a short note in `STATE.md` only if needed.

---

## 17. Final Principle

This is a **brownfield speed-and-efficiency system**.

The best outcome is not the most elaborate process.
The best outcome is:
- correct change
- minimal tokens
- minimal coordination overhead
- repo-consistent implementation
- enough verification to trust it

When in doubt:
**follow an existing pattern, make the smallest safe edit, and stop early once the change is proven.**
