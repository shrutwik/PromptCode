# Practice session architecture

One screen. A library of different projects. Each project is one engineering ticket, shown in full on the left. The assistant proposes changes and does not write them until the person accepts. The report is the tests plus how they used the assistant, shown next to their previous attempt on that same project.

This is the session. It extends `docs/interview-architecture.md`. The eval platform (`challenge.json`, sandbox workers) stays untouched.

## Who it is for

Someone preparing for an interview or an online assessment where an assistant is in the editor. They need to practice the work, not memorize a company’s layout.

The skill, from candidate reports and from CHI 2026, is the same across those rooms: read code you did not write, aim the assistant at one piece, refuse a suggestion that is wrong, run the tests, and explain what you kept. A 2026 study of model judges (TRACE) found they barely beat chance on realistic code, so a model does not grade the session.

## The session

The person picks a task from the library and lands in the editor.

1. The left side shows the whole ticket: the situation, the work, and how to work. Nothing on that panel is withheld for a later click.
2. How to work is an order, not a second set of requirements: run the tests first, then open the code those failures touch, check an assistant suggestion against the file before accepting it, run the tests again, submit when the suite is green.
3. They read the code, change it, and may ask the assistant.
4. They submit. Hidden tests run then and do not add a panel.
5. The report shows the judgment score and the same fields from their previous submitted attempt on this task.

The clock shows time spent. It does not end the session at 60 minutes.

There is one screen for every task. There is no format picker.

## A task

Every task is unique. None is a reskin of another.

| Part | What it is | When they see it |
| --- | --- | --- |
| Situation | Who they are and what broke, in plain language | Always, at the top |
| The work | The whole outcome. The tests already check it | Always, under the situation |
| How to work | What to do first, then next, through submit | Always, under the work |

The ten tasks in `challenges/interview-registry.json` are the catalog. The work differs: a billing incident, a service change, a performance budget, feed consistency, labels across a stack, a shipment merge, tenant isolation, webhook delivery, a pricing refactor, a proration boundary. New tasks are new codebases and new writeups. They are not new session types.

The README in the repo is the same ticket. It does not add requirements the left panel hides, and it does not name the file that contains the change.

Authoring rules:

- Original work. Do not copy a company’s live question or its practice puzzle.
- The failure is something a person would believe in this code. The outcome is behavior the tests already check.
- The assistant’s instructions do not include the buggy line or the patch.
- Solution files, hidden tests, and interviewer notes never enter the workspace copy and never enter the model context.

## The screen

Already present, and kept:

- File tree, editor, chat, test output, accept / edit / reject.
- Library and a brief page before the session starts.
- Report with the rubric, a timeline, the diff, and defend questions.

The left panel is the whole brief: kind, title, situation, the work, and how to work. There is no “step N of M” and no Next step control.

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

The assistant is available for the whole ticket. The product does not turn the chat off to imitate one company’s first checkpoint.

Default instructions for the model:

- The assistant already has the ticket, the tests, and the source files for that question. There is no context picker. Allow orientation, summaries, explanations of supplied files, and clarification of the active question without requiring a hypothesis.
- For debugging and proposed fixes, ask for one hypothesis before suggesting a change. Offer at most a small hint; do not name the bug, the root cause, or the line to change.
- After a test run, explain the failing assertion's expected and observed behavior, give one investigative step, and ask one focused question. Do not provide corrected code, a patch, or the exact fix in that reply, even when directly asked for the answer.
- Do not solve the whole task in one reply.
- A proposed change may be close and wrong.
- Do not use solution files or hidden tests.
- A full-file rewrite of a file the person did not attach is dropped, as is any reply that quotes hidden solution material.
- The local filter accepts bounded orientation phrases and supplied filenames while rejecting recognized unrelated requests and attempts to change or reveal instructions. The model must keep every answer within the active question and supplied codebase, even when an unrelated request mentions code or a supplied filename.
- Off-topic replies use short, varied redirects to the active task. Locally screened refusals still make no provider call.

The brief tells the person, in one line, that the assistant can be wrong. The score does not assume the model obeyed. If it blurts the bug, that reply is still just a suggestion they can reject.

## What is stored

Append-only events on the session, plus the workspace.

Already emitted and kept: file viewed, file changed, prompt, suggestion, accept, modified, reject, test run, final diff viewed, defend answer.

A suggestion that is not yet accepted stores its base revision. Accept compares that to `InterviewSessionFile.revision`.

`attempt_number` increments when the same person starts the same task again. `scoring_version` is `v1` for sessions scored before this score, and `v2` after it. A comparison uses only a previous submit with the same version.

## The score

One number. It is not produced by a model. 100 points from events and the submit tests.

| Field | Points | Rule |
| --- | --- | --- |
| Correctness | 25 | The submit tests passed. |
| Investigation | 15 | They opened the relevant files before the first edit. |
| Fix quality | 10 | The diff stays on this task’s files. Reverting a bad accept helps. |
| AI leverage | 15 | Editing or rejecting a suggestion helps. Accepting one with no later test hurts. |
| Verification | 15 | A test run after each accept or edit-then-accept. |
| Communication | 10 | The defend answer, or a one-line note, says what they kept or rejected. |
| Recovery | 10 | A failing test, then a smaller fix, then a pass. |

The report shows this attempt and the previous submitted attempt on the same task: each field, and the total. If there is no previous attempt, this one is the baseline.

The older prompt-evaluation delta is a different product. This report does not read it.

## Defend

After submit, in order:

1. The task’s existing questions from the solution notes, with guides stripped, as today.
2. At most one more, from a template, for a file they accepted: “Walk through the change you accepted in `{path}`. What would a wrong version still pass?”

No model writes the question. No model scores the answer.

## Catalog

| Task | Situation in one line | The work |
| --- | --- | --- |
| Invoice status | A paid invoice showed as draft | Paid stays paid unless voided. Legal moves still work. Illegal moves return 409. |
| Order hold | Support cannot see why an order is held | The reason survives the next read. Old orders stay null. |
| Catalog suggest | Electronics suggest feels hung | Same ranking, under the latency and scan budget. |
| Notification feed | The unread badge sticks | One mark and two quick marks both match the rows. |
| Workspace labels | Checked labels vanish after save | The API and the screen show the ids that were saved. Unknown ids are rejected. |
| Shipment CSV | A merge scrambled the timeline and doubled a quantity | Time order. One event id counts once. Same status is not a duplicate. |
| Document access | Another tenant’s file opened | Cross-tenant read and update look missing. The owner still works. |
| Webhook retry | A retry charged the customer twice | One charge per delivery. A flush stays bounded. |
| Pricing extract | The price math is correct and buried | `applyRules` matches `quote`. No golden cent moves. |
| Proration | A cancel on the period boundary was still inside the period | The end is outside. The start is inside. Mid-period credits stay. |

## Out of the product

These were considered and rejected.

- A separate screen per company. Meta’s editor, Shopify’s empty repo, and an assessment sandbox train the same skill. The library is the variety.
- A mode that starts from an empty repo.
- A menu of GPT, Claude, Gemini, and Llama.
- A model that writes the grade, including an A/B/C fluency grade.
- Turning the chat off for part of the ticket.
- Revealing the ticket in steps, or a Next step control.
- A voice interviewer, proctoring, and copying a company’s unpublished questions.
- New language runners. Python and Node already run this catalog.

## What the code does

- Library, brief, workspace, starter snapshot, editor, chat, tests by allowlisted command, submit, rubric, defend, attempt number.
- The left panel renders the situation, the work, and how to work from one payload.
- Accept, edit-then-accept, and reject, stored as events. A stale accept is refused.
- Solution files blocked from the candidate and from the model.
- New submits are `scoring_version` `v2`, taken from events. Older reports stay `v1`.
- The report compares this attempt with the previous submitted attempt on the same task and the same scoring version.
- The extra defend question is filled from a path they accepted.

`backend/tests/test_prep_session_architecture.py` and `backend/tests/test_interview_levels.py` cover this.

Host deploy, live OpenAI, and built Docker runner images are outside this section.

## Rules that do not bend

- One screen, many codebases.
- The whole ticket is on the left from the start. How to work only orders that work.
- The model does not write files and does not grade.
- A new task is a new codebase and a new writeup, not a new mode.
