# Ticket labels

You are on tickets. The workspace already has a fixed set of labels. Agents are pasting tags into the title because the labels they check are gone after save, so the queue filters lie.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

A label is an id and a name, scoped to one workspace. A ticket stores label ids.

`PUT /tickets/:id/labels` with ids from that workspace returns those ids, and the next GET returns the same ids. An id that is not in the workspace is rejected with 400.

The ticket screen shows the label ids the server stored.

The export spreadsheet is a hypothesis for where labels went.

## Getting started

```bash
npm install
npm test
```

## Investigation checkpoints

This ticket tests: Validated workspace ids must survive storage, response serialization and later component hydration. Verification focus: Verify selected checkboxes after PUT, GET and remount; clear all labels; reject mixed valid/foreign lists without changing prior labels. Checkpoint 1: Reproduce the reported behavior and state the contract invariant. Checkpoint 2: Repair the smallest relevant path and verify preservation on success and rejection. Checkpoint 3: Defend your change with a counterexample and discuss the explicitly optional changed requirement.

## Optional review extension

Discuss deleting a label while a user edits a ticket and how to expose the conflict; do not silently add that behavior to the baseline. This is discussion-only and does not alter baseline acceptance tests. Keep the supplied tests and configuration intact; use scratch.py or scratch.ts for independent experiments. Explain what you asked the assistant to do and which assumption you verified.
