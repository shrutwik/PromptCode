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
