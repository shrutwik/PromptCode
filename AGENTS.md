# AGENTS.md for Codex

> Place the **AGENTS.md** section below into your repo root as `AGENTS.md`.
> Use the **Task Prompt** section as your per-run instruction when you want Codex to do a hardening pass.

---

## AGENTS.md

```md
# AGENTS.md — Existing Repo / Low-Credit High-Efficiency Mode

> This repository already exists.
> You are adding to it, fixing it, or hardening it.
> Your job is to understand what exists, make the smallest safe change, verify efficiently, and preserve existing behavior.
> Optimize for least token usage, least context bloat, and maximum useful progress.

## Core Objective

Use the fewest possible tokens and credits to make the correct change in an existing codebase.

Priority order:
1. Correctness
2. Preserve existing behavior
3. Match existing patterns
4. Minimize token/credit use
5. Keep context small

## Cardinal Rules

1. **Read before you write**
   - Find the closest existing implementation before changing anything.
   - Prefer existing code as the spec.

2. **Plan before changing**
   - Always create a short written plan, even for small work.
   - Keep the plan brief and execution-focused.

3. **Match the codebase**
   - Reuse naming, file layout, validation, error handling, utilities, and tests already present.
   - Do not introduce new patterns when an existing one works.

4. **Use the cheapest sufficient approach**
   - Read the minimum files needed.
   - Run the minimum verification needed.
   - Do not do broad rewrites when a small patch will solve it.

5. **Keep context lean**
   - Do not read the whole repo unless strictly necessary.
   - Summarize findings instead of repeating code.
   - Prefer paths and concise notes over pasting file contents.

6. **Change one thing at a time**
   - Make one logical fix, verify it, then move to the next.
   - Keep commits and reasoning atomic.

7. **Do not break working code**
   - Preserve existing behavior unless the task explicitly requires behavior change.
   - Be conservative around shared utilities, auth, data access, and routing.

8. **Avoid unnecessary questions**
   - If the existing codebase provides the pattern, follow it.
   - Ask only when blocked by a real ambiguity that cannot be resolved from the repo.

## Brownfield Workflow

### 1. Understand first
Before editing:
- identify the issue
- find the closest existing pattern
- read 1–2 reference files only
- identify likely blast radius
- note possible regressions

### 2. Plan briefly
For every task, write a short plan in the response:
- goal
- references
- files to change
- minimal verification

### 3. Execute surgically
- change the minimum number of files
- prefer extending existing helpers over creating new abstractions
- avoid unrelated cleanup
- avoid refactors unless required for the fix

### 4. Verify efficiently
Run the smallest verification that proves correctness:
1. targeted test or command
2. lint/typecheck for touched area if relevant
3. broader verification only if risk justifies it

## Token and Credit Economy Rules

Always prefer:
- grep/search over opening many files
- 1 reference file over 10
- a minimal patch over a rewrite
- targeted verification over full-suite verification
- one good pass over repeated speculative passes

Never do this by default:
- read the entire repository
- open large unrelated files
- perform broad refactors during hardening
- run the full test suite after every small edit
- touch unrelated code for style cleanup
- restate long reasoning when a concise note is enough

## Severity-First Hardening Policy

When asked to harden the repo:
- prioritize by severity first
- then by safest/highest-confidence fix
- then by smallest blast radius

Fix order preference:
1. security and auth issues
2. data loss / corruption risks
3. crashers and broken flows
4. validation and unsafe input handling
5. reliability and error-handling gaps
6. maintainability issues only when directly related

Do not chase low-severity cleanup while higher-severity safe fixes remain.

## Existing-Repo Pattern Matching

Before creating or changing anything, look for:
- similar routes
- similar services
- similar components
- similar tests
- similar error handling
- similar validation

If multiple patterns exist, prefer:
- the most recent non-legacy pattern
- the pattern used in adjacent code
- the simpler pattern unless the task requires the more complex one

If the repo has inconsistent patterns, explicitly name which reference file you are following.

## Verification Rules

For each completed item, report:
- what issue was fixed
- files changed
- minimal verification performed
- any risk or follow-up note

Do not claim certainty without verification.

## Output Style

Keep output concise and execution-focused.

For each item use:
- Issue
- Reference
- Change
- Verification

After the requested batch is complete, stop and provide a checkpoint.

## Stop Conditions

Stop and ask only if:
- the task is blocked by missing requirements
- the safest fix depends on a product decision not inferable from the repo
- verification cannot be performed with available tools

Otherwise proceed using the closest existing pattern.

## Repo-Specific Notes

Fill these in for each repository when possible:
- Stack:
- Key entry points:
- Canonical route pattern:
- Canonical service pattern:
- Canonical test pattern:
- Do-not-touch paths:
- Important commands:

## Final Principle

Make the smallest safe change that materially improves the codebase.
Use existing code as the guide.
Spend credits carefully.
Stop after the requested batch and checkpoint.
```

---

## Task Prompt

Copy and paste this prompt into Codex when you want it to do a hardening pass using the `AGENTS.md` above.

```text
Follow the repository’s AGENTS.md exactly.

Work in existing-repo hardening mode:
- make code changes directly in the files
- preserve existing behavior and patterns
- use the least amount of context, reasoning, and verification needed to make safe progress
- prioritize issues by severity, then by safest/highest-value fix
- make changes one by one, not as a broad rewrite
- after each change, run the smallest verification that proves the fix
- do not introduce new patterns if an existing one can be followed
- do not touch unrelated code

Do exactly 4 hardening items in this round.

For each item:
1. identify the issue and why it matters
2. find the closest existing pattern/reference in the repo
3. apply the minimal safe patch
4. verify it
5. briefly summarize what changed

After the 4th item, stop and give a checkpoint with:
- the 4 issues addressed
- files changed
- verification performed
- remaining higher-severity items worth doing next

Do not keep going past 4 items.
Do not ask unnecessary questions unless blocked by a real ambiguity.
Keep output concise and execution-focused.
```
