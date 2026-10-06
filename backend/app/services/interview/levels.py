"""One interview ticket per challenge. The suite is the bar."""

from __future__ import annotations

from typing import Any

# Each task is one engineering ticket. The kind is the work.
# problem and body are the whole brief. guide is the order of work, not hidden requirements.
GUIDE = [
    "First, read the codebase and run the tests so you can see what fails.",
    "Then, open the code those failures touch. Ask the assistant about one piece, and check the suggestion against the file before you accept it.",
    "Then, run the tests again and read the failure before the next edit.",
    "Submit when the suite is green. You will be asked what you kept and what you rejected.",
]
TASKS: dict[str, dict[str, Any]] = {
    "invoice-status-transition": {
        "problem": (
            "You are the billing engineer on call before month-end close. "
            "Finance collected invoice inv_paid, then this service showed it as draft. "
            "Draft is the editable state, so a paid invoice that looks like a draft can change after money has moved. "
            "Work in this repo with the assistant. A suggestion is a draft until the tests agree."
        ),
        "levels": [
            {
                "kind": "incident",
                "title": "Invoice status",
                "body": (
                    "A paid invoice stays paid unless it is voided. Void is the cancellation that keeps a paper trail. "
                    "These moves still succeed: draft to sent, draft to void, sent to paid, sent to void, and paid to void. "
                    "Void is terminal. A status moved onto itself is not a transition. "
                    "POST /invoices/:id/transition returns 409 when the move is illegal, including sent back to draft, and the stored status stays as it was. "
                    "A missing invoice is a different failure from an illegal move. "
                    "Statuses are draft, sent, paid, and void. Amounts are integer cents. "
                    "A teammate says last sprint’s date formatter rewrote the status. That is a hypothesis. Run npm test."
                ),
            },
        ],
    },
    "order-hold-reason": {
        "problem": (
            "You are on the orders API during a warehouse freeze. "
            "Support puts an order on hold with a reason, then the next read cannot say why it is held, or the hold does not survive a refresh. "
            "Orders created before this field existed are still in the database. "
            "Work in this repo with the assistant. A suggestion is a draft until the tests agree."
        ),
        "levels": [
            {
                "kind": "change",
                "title": "Order hold",
                "body": (
                    "POST /orders/:id/hold with a hold_reason stores that reason and returns the order as on_hold. "
                    "The following GET returns the same reason. "
                    "POST /orders/:id/release returns the order as open. "
                    "Orders that never had a reason come back with hold_reason null. "
                    "Money is total_cents, an integer. "
                    "People are blaming the metrics counter. That is a hypothesis. Run pytest -q."
                ),
            },
        ],
    },
    "catalog-suggest-latency": {
        "problem": (
            "You are on catalog search. Shoppers typing in electronics wait long enough that suggest feels hung. "
            "Product will ship a faster list only if it ranks the same products in the same order as today. "
            "The catalog in this repo is in memory, about 10,000 products, with id, title, category, popularity, and tokens. "
            "Work in this repo with the assistant. A suggestion is a draft until the tests agree."
        ),
        "levels": [
            {
                "kind": "performance",
                "title": "Search suggest",
                "body": (
                    "suggest stays in the current rank order: higher score, then higher popularity, then id ascending. "
                    "On the 10,000-product catalog the tests build, a query finishes in under 200ms and the scan counter stays under 20,000. "
                    "A cache in front of suggest is a hypothesis. Measure the work a query does before you add one. Run npm test."
                ),
            },
        ],
    },
    "notification-feed-stale": {
        "problem": (
            "You are on the notification feed. A user marks an item read and the unread badge stays. "
            "Two quick marks are worse: one of them disappears, and the badge does not match the rows. "
            "Support has a screenshot of a badge that says 2 while the visible rows say read. "
            "Work in this repo with the assistant. A suggestion is a draft until the tests agree."
        ),
        "levels": [
            {
                "kind": "consistency",
                "title": "Notification feed",
                "body": (
                    "unreadCount is how many notifications have read set to false. "
                    "After the feed loads, the badge shows that count. "
                    "Marking one item read leaves that row read and drops the badge by one. "
                    "Marking two items read together leaves both rows read, and the badge matches when both calls finish. "
                    "A row that was already read stays read. "
                    "Someone says the React list key is wrong. That is a hypothesis. Run npm test."
                ),
            },
        ],
    },
    "workspace-label-propagation": {
        "problem": (
            "You are on tickets. The workspace already has a fixed set of labels. "
            "Agents are pasting tags into the title because the labels they check are gone after save, so the queue filters lie. "
            "Work in this repo with the assistant. A suggestion is a draft until the tests agree."
        ),
        "levels": [
            {
                "kind": "change",
                "title": "Ticket labels",
                "body": (
                    "A label is an id and a name, scoped to one workspace. A ticket stores label ids. "
                    "PUT /tickets/:id/labels with ids from that workspace returns those ids, and the next GET returns the same ids. "
                    "An id that is not in the workspace is rejected with 400. "
                    "The ticket screen shows the label ids the server stored. "
                    "The export spreadsheet is a hypothesis for where labels went. Run npm test."
                ),
            },
        ],
    },
    "shipment-csv-merge": {
        "problem": (
            "You own the nightly shipment merge. Warehouse drops two CSV files that landed out of order. "
            "A shipment timeline showed a later status before an earlier one, and a quantity that should have been counted once was counted twice. "
            "Ops almost shorted a replenishment on the doubled count. "
            "Work in this repo with the assistant. A suggestion is a draft until the tests agree."
        ),
        "levels": [
            {
                "kind": "incident",
                "title": "Shipment CSV",
                "body": (
                    "Events from separate files come out in timestamp order for each shipment. "
                    "The same event_id in two files counts once. total quantity is what ops ships against. "
                    "Two events with the same status and different ids both stay, in timestamp order. "
                    "A shipment can be in_transit in two different events. "
                    "A teammate thinks a comma inside a CSV field broke the parser. That is a hypothesis. Run pytest -q."
                ),
            },
        ],
    },
    "tenant-document-acl": {
        "problem": (
            "You are on documents. Someone at Acme opened /documents/doc_globex_1 and received Globex’s title and body. "
            "They should not learn that the file exists. Acme and Globex are two tenants. "
            "Each request carries a bearer token that maps to a user and a tenant. "
            "Work in this repo with the assistant. A suggestion is a draft until the tests agree."
        ),
        "levels": [
            {
                "kind": "security",
                "title": "Document access",
                "body": (
                    "GET and PATCH for a document id from another tenant respond 404. The body does not include that tenant’s title or text. "
                    "A missing id is also 404. "
                    "Acme can still GET its own documents, and the list route still returns only the caller’s tenant. "
                    "Globex can still read Globex documents. "
                    "A missing or unknown token is 401. "
                    "People will blame a CDN cache. That is a hypothesis. Run pytest -q."
                ),
            },
        ],
    },
    "webhook-delivery-retry": {
        "problem": (
            "You are on outbound webhooks. Receivers sometimes answer 500, and the worker retries. "
            "Finance then sees the charge recorded twice for one delivery. "
            "A flush of the pending queue also made staging fall over. "
            "Delivery is at-least-once. A retry after a 5xx is normal. "
            "Work in this repo with the assistant. A suggestion is a draft until the tests agree."
        ),
        "levels": [
            {
                "kind": "delivery",
                "title": "Webhook retry",
                "body": (
                    "A delivery that fails and then succeeds still records the charge once for that delivery id. "
                    "Attempts stop at the retry policy’s max. "
                    "Flushing a batch keeps at most about five posts in flight at once. "
                    "Lowering the timeout is a hypothesis. The duplicate charge is the incident. Run npm test."
                ),
            },
        ],
    },
    "pricing-rule-extract": {
        "problem": (
            "You are in pricing. Quotes are correct, and finance trusts the golden cents. "
            "The rule loop is buried inside quote(), and the next pricing change is unsafe until that loop can be read on its own. "
            "Percent-off and amount-off do not commute once you round. "
            "Work in this repo with the assistant. A suggestion is a draft until the tests agree."
        ),
        "levels": [
            {
                "kind": "refactor",
                "title": "Pricing rules",
                "body": (
                    "Add applyRules(baseCents, rules). It applies percent_off, then amount_off, then surcharge_percent, with the same half-up rounding, and returns the same finalCents and applied codes as quote(). "
                    "quote() calls applyRules and keeps its current signature. "
                    "A negative result floors at 0. An empty rule list returns the base. "
                    "If a golden cent moves, the extract is wrong. Leave the expectations alone. Run npm test."
                ),
            },
        ],
    },
    "subscription-proration-boundary": {
        "problem": (
            "You are on subscriptions. A customer canceled exactly when the billing period rolled and the books treated that instant as still inside the period. "
            "Support thinks the Chicago clock display is wrong again. "
            "The credit is computed from the stored period and the cancel instant. The display helper only formats that instant. "
            "Work in this repo with the assistant. A suggestion is a draft until the tests agree."
        ),
        "levels": [
            {
                "kind": "incident",
                "title": "Period boundary",
                "body": (
                    "The instant at period end is outside the period and credits nothing. "
                    "The instant at period start is inside. A cancel in the middle of the period still gets a credit. "
                    "A cancel before the period credits nothing. "
                    "The tests that already describe those cases stay as they are. Leave them alone and make the boundary agree with them. Run pytest -q."
                ),
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
        "guide": list(GUIDE),
        "can_advance": index < len(levels) - 1 and tests_on_step > 0,
        "is_last": index == len(levels) - 1,
        "earlier": earlier,
    }
