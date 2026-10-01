"""One step at a time. Future feature levels are not included in the payload."""

from __future__ import annotations

from typing import Any

# Each task: a situation, then a bug, then feature levels in order.
# Bodies are the only instructions for that step. Do not mention later steps.
TASKS: dict[str, dict[str, Any]] = {
    "invoice-status-transition": {
        "problem": "You cover billing today. Finance says invoice inv_paid was paid in Stripe and then showed up as draft again. They want it stable before the next close.",
        "levels": [
            {
                "kind": "bug",
                "title": "The paid invoice flipped",
                "body": "inv_paid must not go back to draft. Someone will tell you it is the timezone formatting from last sprint. Check the status rules first. A paid invoice stays paid unless it is voided.",
            },
            {
                "kind": "feature",
                "title": "Feature 1 — legal moves still work",
                "body": "Draft can go to sent, sent can go to paid, and paid can go to void. Void has nowhere left to go. Do not break those paths while you block the bad one.",
            },
            {
                "kind": "feature",
                "title": "Feature 2 — the API refuses a bad move",
                "body": "POST /invoices/:id/transition returns 409 when the move is illegal, including sent back to draft. The invoice stays where it was.",
            },
        ],
    },
    "order-hold-reason": {
        "problem": "You are on the orders API. Support puts orders on hold and then cannot tell a teammate why. Old rows in the database have no reason at all.",
        "levels": [
            {
                "kind": "bug",
                "title": "The hold does not stick",
                "body": "Holding an order and releasing it must persist. A reason written on hold has to still be there after you read the order back. Releasing clears the hold.",
            },
            {
                "kind": "feature",
                "title": "Feature 1 — save hold_reason",
                "body": "POST /orders/:id/hold stores hold_reason. The value you saved is the value you read. Empty and missing are not the same as a real reason.",
            },
            {
                "kind": "feature",
                "title": "Feature 2 — old orders stay null",
                "body": "GET returns hold_reason. Orders that never had a reason come back null, not an empty string and not a made-up default.",
            },
        ],
    },
    "catalog-suggest-latency": {
        "problem": "You are on catalog. Typing in electronics makes suggest() feel hung. Product wants the same ranking shoppers see today, only faster.",
        "levels": [
            {
                "kind": "bug",
                "title": "Suggest is doing too much work",
                "body": "A query scans far more of the catalog than it should. The scan counter in the tests is the evidence. Caching is a guess people will offer you. Measure the scan before you add a cache.",
            },
            {
                "kind": "feature",
                "title": "Feature 1 — same order, less work",
                "body": "Results stay in the current rank order. Tie breaks stay as they are. You are changing how the work is done, not which product wins.",
            },
            {
                "kind": "feature",
                "title": "Feature 2 — hit the budget",
                "body": "The latency and scan budgets in the tests have to pass on the large catalog, including the electronics queries that hang today.",
            },
        ],
    },
    "notification-feed-stale": {
        "problem": "You are on the notification feed. You mark items read and the unread badge stays. It gets worse if you click two of them quickly.",
        "levels": [
            {
                "kind": "bug",
                "title": "The badge sticks",
                "body": "Marking an item read has to update the row and the unread count. A React key is the rumor. Watch what happens to state when the request comes back.",
            },
            {
                "kind": "feature",
                "title": "Feature 1 — one mark, one update",
                "body": "After a successful mark-as-read, that item shows as read and the badge drops by one. A failed mark does not pretend it worked.",
            },
            {
                "kind": "feature",
                "title": "Feature 2 — two quick clicks",
                "body": "Marking two items read in a row must not drop one of the updates. Both rows and the badge match the server when the clicks finish.",
            },
        ],
    },
    "workspace-label-propagation": {
        "problem": "You are on tickets. The workspace already has a fixed set of labels. People are pasting free-text tags into tickets because the real labels never show up.",
        "levels": [
            {
                "kind": "bug",
                "title": "Labels disappear on save",
                "body": "Choosing workspace labels and saving the ticket must keep those label ids. A ticket that had labels still has them when you load it again.",
            },
            {
                "kind": "feature",
                "title": "Feature 1 — only real labels",
                "body": "Reject a label id that is not in this workspace. Do not store free-text tags beside the real ids.",
            },
            {
                "kind": "feature",
                "title": "Feature 2 — the API matches",
                "body": "PUT and GET return the same labelIds. The list is the workspace labels you saved, in a stable order.",
            },
            {
                "kind": "feature",
                "title": "Feature 3 — the screen matches the API",
                "body": "The ticket UI shows the labels the server stored. After a save, the screen and GET tell the same story.",
            },
        ],
    },
    "shipment-csv-merge": {
        "problem": "You own the nightly shipment merge. Two days of CSV landed out of order, and a quantity that should have been counted once was counted twice.",
        "levels": [
            {
                "kind": "bug",
                "title": "The timeline is scrambled",
                "body": "Events from different files have to come out in timestamp order. A comma inside a CSV field is the rumor. Get the order right before you rewrite the parser.",
            },
            {
                "kind": "feature",
                "title": "Feature 1 — one event, one count",
                "body": "The same event_id in two files counts once. Quantity must not double because the file was merged twice.",
            },
            {
                "kind": "feature",
                "title": "Feature 2 — same status is not a duplicate",
                "body": "Two events with the same status and different ids both stay. Deduping is by event id, not by status text.",
            },
        ],
    },
    "tenant-document-acl": {
        "problem": "You are on documents. Someone at Acme opened /documents/doc_globex_1 and saw Globex’s file. They should not learn that the file exists.",
        "levels": [
            {
                "kind": "bug",
                "title": "The other tenant’s file opened",
                "body": "A document id from another org must not return content. People will blame the CDN. Check which tenant the request is allowed to see.",
            },
            {
                "kind": "feature",
                "title": "Feature 1 — hide it",
                "body": "Cross-tenant GET responds 404, not 403. The body does not include the other tenant’s title or text.",
            },
            {
                "kind": "feature",
                "title": "Feature 2 — same tenant still works",
                "body": "Acme can still GET and PATCH its own documents. A fix that blocks everyone is not done.",
            },
        ],
    },
    "webhook-delivery-retry": {
        "problem": "You are on webhooks. A 5xx retries the delivery, finance sees the charge twice, and a flush of the queue melts staging.",
        "levels": [
            {
                "kind": "bug",
                "title": "The retry charged them twice",
                "body": "Retrying a delivery must not run the side effect again when that delivery already succeeded once. Stop the duplicate before you tune throughput.",
            },
            {
                "kind": "feature",
                "title": "Feature 1 — a retry is safe",
                "body": "A second attempt for the same delivery does not double-apply. Failures that never succeeded can still be retried.",
            },
            {
                "kind": "feature",
                "title": "Feature 2 — don’t fire the whole queue",
                "body": "Flushing pending deliveries runs about five at a time, not the entire batch at once.",
            },
        ],
    },
    "pricing-rule-extract": {
        "problem": "You are in pricing. Quotes are correct. The rule loop is buried in quote(), and the next change will be risky until that loop has a name.",
        "levels": [
            {
                "kind": "bug",
                "title": "A careless extract changes the price",
                "body": "Pulling the loop out must not change a single quoted cent. If a golden test moves, the extract is wrong, not the test. Do not edit the expectations.",
            },
            {
                "kind": "feature",
                "title": "Feature 1 — applyRules",
                "body": "Add applyRules(baseCents, rules). It applies the rules in the same order, with the same rounding, and returns the same cents the loop returns today.",
            },
            {
                "kind": "feature",
                "title": "Feature 2 — quote uses it",
                "body": "quote() calls applyRules and keeps its current signature. Callers do not change. The goldens stay green.",
            },
        ],
    },
    "subscription-proration-boundary": {
        "problem": "You are on subscriptions. A customer canceled exactly when the period rolled and got a credit they should not have. Support thinks the Chicago clock display is wrong again.",
        "levels": [
            {
                "kind": "bug",
                "title": "The credit at the boundary is wrong",
                "body": "Canceling exactly at period end credits nothing. The public tests you already have can stay green while this case is still wrong. The display timezone is the rumor. Check how the period end is treated.",
            },
            {
                "kind": "feature",
                "title": "Feature 1 — the end is exclusive",
                "body": "Time inside the period still prorates. The instant at period.end is not inside the period.",
            },
            {
                "kind": "feature",
                "title": "Feature 2 — the tests you were given stay green",
                "body": "The existing unit tests pass without edits. The boundary case and the older cases agree.",
            },
        ],
    },
}


def task_for(slug: str) -> dict[str, Any] | None:
    task = TASKS.get(slug)
    if not task:
        return None
    return task


def level_view(slug: str, index: int, *, tests_on_step: int) -> dict[str, Any] | None:
    task = task_for(slug)
    if not task:
        return None
    levels = task["levels"]
    index = max(0, min(index, len(levels) - 1))
    current = levels[index]
    earlier = [
        {
            "index": i,
            "kind": levels[i]["kind"],
            "title": levels[i]["title"],
            "body": levels[i]["body"],
        }
        for i in range(index)
    ]
    return {
        "index": index,
        "total": len(levels),
        "kind": current["kind"],
        "title": current["title"],
        "body": current["body"],
        "problem": task["problem"],
        "can_advance": index < len(levels) - 1 and tests_on_step > 0,
        "is_last": index == len(levels) - 1,
        "earlier": earlier,
    }
