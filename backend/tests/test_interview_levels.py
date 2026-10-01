from app.services.interview.levels import TASKS, level_view


def test_every_task_has_a_bug_then_feature_levels():
    assert len(TASKS) == 10
    problems = set()
    for slug, task in TASKS.items():
        problems.add(task["problem"])
        kinds = [level["kind"] for level in task["levels"]]
        assert kinds[0] == "bug", slug
        assert "feature" in kinds[1:], slug
        assert len({level["title"] for level in task["levels"]}) == len(task["levels"])
    assert len(problems) == 10


def test_future_levels_are_not_in_the_view():
    view = level_view("invoice-status-transition", 0, tests_on_step=0)
    assert view["title"].startswith("The paid invoice")
    assert view["can_advance"] is False
    assert "409" not in view["body"]
    nxt = level_view("invoice-status-transition", 0, tests_on_step=1)
    assert nxt["can_advance"] is True
    last = level_view("workspace-label-propagation", 99, tests_on_step=3)
    assert last["is_last"] is True
    assert last["can_advance"] is False
