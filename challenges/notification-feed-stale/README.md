# Notification feed

You are on the notification feed. A user marks an item read and the unread badge stays. Two quick marks are worse: one of them disappears, and the badge does not match the rows.

Support has a screenshot of a badge that says 2 while the visible rows say read.

Use the assistant in this session. Check what it tells you against the code, then run the tests.

## Done

The unread count is how many notifications have `read` set to false. After the feed loads, the badge shows that count.

Marking one item read leaves that row read and drops the badge by one. Marking two items read together leaves both rows read, and the badge matches when both calls finish. A row that was already read stays read.

Someone says the React list key is wrong. That is a hypothesis.

## Getting started

```bash
npm install
npm test
```
