# Practice session architecture

One screen. A library of different projects. Each project is a situation, a bug, and feature levels that open one at a time. The assistant proposes changes and does not write them until the person accepts. The report is the tests plus how they used the assistant, shown next to their previous attempt on that same project.

This document is the plan. It does not authorize implementation by itself.

It extends the session already described in `docs/interview-architecture.md`. The eval platform (`challenge.json`, sandbox workers) stays untouched.

## Who it is for

Someone preparing for an interview or an online assessment where an assistant is in the editor. They need to practice the work, not memorize a company’s layout.

The skill, from candidate reports and from CHI 2026, is the same across those rooms: read code you did not write, aim the assistant at one piece, refuse a suggestion that is wrong, run the tests, and explain what you kept. A 2026 study of model judges (TRACE) found they barely beat chance on realistic code, so a model does not grade the session.

## The session

The person picks a task from the library and lands in the editor.

1. The task shows the situation and only the current step.
2. They read the code, change it, and may ask the assistant.
3. They run the tests for this step. That unlocks the next step. A failing run still unlocks it, because the suite covers later levels and must not trap them on step one.
4. The next step’s text appears. Earlier steps stay visible. Later steps do not.
5. On the last step they submit. Hidden tests run then and do not add another step.
6. The report shows steps reached, the judgment score, and both numbers from their previous submitted attempt on this task.

The clock shows time spent. It does not end the session at 60 minutes.

There is one screen for every task. There is no format picker.

## A task

Every task is unique. None is a reskin of another.

| Part | What it is | When they see it |
| --- | --- | --- |
| Situation | Who they are and what broke, in plain language | Always, above the step |
| Bug | The first step. One real failure in this codebase | Step 1 |
| Feature levels | The rest of the work, in order. Each level is one behavior | One at a time, after a test run on the previous step |

A task has at least the bug and one feature level. It may have more feature levels. The count belongs to that task. Workspace labels have three feature levels. Most others have two.

The ten tasks in `challenges/interview-registry.json` are the catalog. Stacks already differ: TypeScript services, a React feed, Python APIs, a CSV merge, a pricing module. New tasks are new codebases and new writeups. They are not new session types.

The README in the repo is the situation and how to run tests. It does not list later feature levels. Those lines live only in the step payload the server sends for the current step.

Authoring rules:

- Original work. Do not copy a company’s live question or its practice puzzle.
- The bug is something a person would believe in this code. The feature levels are behaviors the tests already check.
- The assistant’s instructions do not include the buggy line, the patch, or the text of later steps.
- Solution files, hidden tests, and interviewer notes never enter the workspace copy and never enter the model context.

## The screen

Already present, and kept:

- File tree, editor, chat, test output, accept / edit / reject.
- Library and a brief page before the session starts.
- Report with the rubric, a timeline, the diff, and defend questions.

The task panel is the step card: situation, “step N of M”, the current title and body, and Next step. Next step stays disabled until this step has a test run. The last step says to submit.

Test output appends. A Clear control empties it. The person can miss a failure if the log wipes itself.

## The assistant

One assistant. No menu of models.

A reply is an explanation. When it proposes a change, that change is a suggestion: path, the file revision it was based on, and the proposed body. Nothing is written until the person acts.

| Action | What is stored | What happens to the file |
| --- | --- | --- |
| Accept | `ai_edit_accepted` | Written, only if the file revision is still the suggestion’s base revision |
| Edit, then accept | `ai_edit_modified`, both bodies | The editor buffer is written, under the same revision check |
| Reject | `ai_edit_rejected` | Nothing |

A stale accept fails. The person re-asks or edits by hand.

The assistant is available on every step, including the bug. The product does not turn the chat off to imitate one company’s first checkpoint.

Default instructions for the model:

- Do not name the bug, the root cause, or the line to change.
- Do not solve the whole step in one reply.
- A proposed change may be close and wrong.
- Do not use solution files, hidden tests, or steps the person has not reached.

The task tells the person, in one line, that the assistant can be wrong. The score does not assume the model obeyed. If it blurts the bug, that reply is still just a suggestion they can reject.

## What is stored

Append-only events on the session, plus the workspace.

Already emitted and kept: file viewed, file changed, prompt, suggestion, accept, modified, reject, test run, final diff viewed, defend answer.

Added for steps: `level_advanced`, with the index they left. The current step is the count of those events. Tests on this step are the test runs since the last advance.

A suggestion that is not yet accepted stores its base revision. Accept compares that to `InterviewSessionFile.revision`.

`attempt_number` increments when the same person starts the same task again. `scoring_version` is `v1` for sessions scored before this plan’s score change, and `v2` after it. A comparison uses only a previous submit with the same version.

## The score

Two lines. Neither is produced by a model.

**Steps.** How many steps they opened, out of the task’s total. Opening a step requires a test run on the one before it. Skipping does not exist. Hidden tests at submit do not add a step.

**Judgment.** 100 points from events and the submit tests.

| Field | Points | Rule |
| --- | --- | --- |
| Correctness | 25 | The submit tests passed. |
| Investigation | 15 | They opened the relevant files before the first edit. |
| Fix quality | 10 | The diff stays on this task’s files. Reverting a bad accept helps. |
| AI leverage | 15 | Editing or rejecting a suggestion helps. Accepting one with no later test on that step hurts. |
| Verification | 15 | A test run after each accept or edit-then-accept. |
| Communication | 10 | The defend answer, or a one-line note, says what they kept or rejected. |
| Recovery | 10 | A failing test, then a smaller fix, then a pass. |

Steps are not added into the 100. The report shows this attempt and the previous submitted attempt on the same task: steps, each field, and the total. If there is no previous attempt, this one is the baseline.

The older prompt-evaluation delta is a different product. This report does not read it.

## Defend

After submit, in order:

1. The task’s existing questions from the solution notes, with guides stripped, as today.
2. At most one more, from a template, for a file they accepted: “Walk through the change you accepted in `{path}`. What would a wrong version still pass?”

No model writes the question. No model scores the answer.

## Catalog

| Task | Situation in one line | Bug, then feature levels |
| --- | --- | --- |
| Invoice status | A paid invoice showed as draft | Block the illegal move. Keep legal moves. API returns 409. |
| Order hold | Support cannot see why an order is held | The hold must stick. Save the reason. Old orders stay null. |
| Catalog suggest | Electronics suggest feels hung | Too much scanning. Same ranking. Hit the budget. |
| Notification feed | The unread badge sticks | One mark updates the badge. Two quick marks both stick. |
| Workspace labels | Free-text tags instead of real labels | Labels survive a save. Only real ids. API matches. Screen matches. |
| Shipment CSV | A merge scrambled the timeline and doubled a quantity | Order by time. Same event id counts once. Same status is not a duplicate. |
| Document access | Another tenant’s file opened | Hide it as 404. The owner can still read and update. |
| Webhook retry | A retry charged the customer twice | Do not repeat a success. Flush about five at a time. |
| Pricing extract | The price math is correct and buried | An extract must not change cents. `applyRules` exists. `quote` calls it. |
| Proration | A cancel on the period boundary credited the wrong amount | The boundary credits nothing. The end is exclusive. Older tests stay green. |

## Out of the product

These were considered and rejected.

- A separate screen per company. Meta’s editor, Shopify’s empty repo, and an assessment sandbox train the same skill. The library is the variety.
- A mode that starts from an empty repo.
- A menu of GPT, Claude, Gemini, and Llama.
- A model that writes the grade, including an A/B/C fluency grade.
- Turning the chat off for the first step.
- A voice interviewer, proctoring, and copying a company’s unpublished questions.
- New language runners. Python and Node already run this catalog.

## What the code already does

- Library, brief, workspace, starter snapshot, editor, chat, tests by allowlisted command, submit, rubric, defend, attempt number.
- Accept, edit-then-accept, and reject, stored as events.
- Solution files blocked from the candidate and from the model.
- All ten tasks have a situation, a bug step, and feature levels. The task shows one step. Next step unlocks after a test run. The README does not list later levels.

## What this plan still requires

These five are in place. `backend/tests/test_prep_session_architecture.py` covers them (9 tests).

1. Stale accept is refused: accept checks the file revision. Reject still writes nothing.
2. Assistant instructions withhold the bug and the rest of the step, and may return a close-but-wrong change.
3. New submits are `scoring_version` `v2`, taken from events. Older reports stay `v1`.
4. The report compares this attempt with the previous submitted attempt on the same task and the same scoring version.
5. The extra defend question is filled from a path they accepted.

Host deploy, live OpenAI, and built Docker runner images are outside this section.

## Rules that do not bend

- One screen, many codebases.
- Later step text is not in the page, the README, or the model context.
- The model does not write files and does not grade.
- A new task is a new codebase and a new writeup, not a new mode.
