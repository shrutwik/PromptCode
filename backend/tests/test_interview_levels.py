from app.services.interview.levels import TASKS, level_view

WORK = {"incident", "change", "performance", "consistency", "security", "delivery", "refactor"}


def test_each_task_is_one_engineering_ticket():
    assert len(TASKS) == 10
    problems = set()
    for slug, task in TASKS.items():
        problems.add(task["problem"])
        levels = task["levels"]
        assert len(levels) == 1, slug
        kind = levels[0]["kind"]
        assert kind in WORK, slug
        assert kind not in {"bug", "feature"}, slug
        assert "Feature" not in levels[0]["title"]
        assert "npm test" in levels[0]["body"] or "pytest -q" in levels[0]["body"]
    assert len(problems) == 10


def test_the_ticket_is_the_whole_ask():
    view = level_view("invoice-status-transition", 0, tests_on_step=0)
    assert view["title"] == "Invoice status"
    assert view["is_last"] is True
    assert view["can_advance"] is False
    assert "409" in view["body"]
    assert view["guide"][0].startswith("First,")
    assert len(view["guide"]) == 4
    after_tests = level_view("invoice-status-transition", 0, tests_on_step=1)
    assert after_tests["can_advance"] is False
    assert after_tests["guide"] == view["guide"]
    last = level_view("workspace-label-propagation", 99, tests_on_step=3)
    assert last["is_last"] is True
    assert last["kind"] == "change"
    assert last["guide"][0].startswith("First,")
