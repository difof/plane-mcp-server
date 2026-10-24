"""Guard against the server's silent assignee replacement footgun."""

from types import SimpleNamespace


def _page(*members):
    return SimpleNamespace(
        results=[SimpleNamespace(id=id, is_active=active, role=role) for id, active, role in members],
        next_page_results=False,
        next_cursor=None,
    )


def test_valid_assignee_is_passed_to_the_sdk(registered, spy):
    spy.returns["projects.get_members_lite"] = _page(("member", True, 15))
    registered["workitem"].fn(action="update", project_id="p", workitem_id="w", assignees=["member"])
    assert spy.recorder.methods == ["projects.get_members_lite", "work_items.update"]


def test_non_member_can_never_clear_previous_assignees(registered, spy):
    spy.returns["projects.get_members_lite"] = _page(("old", True, 15), ("guest", True, 5), ("inactive", False, 20))
    spy.returns["work_items.retrieve"] = SimpleNamespace(assignees=["old"])
    for bad in ("nonmember", "guest", "inactive"):
        spy.recorder.calls.clear()
        result = registered["workitem"].fn(action="manage_assignee", project_id="p", workitem_id="w", add_user_id=bad)
        assert result.startswith("Error:") and bad in result
        assert spy.recorder.methods == ["work_items.retrieve", "projects.get_members_lite"]


def test_create_refuses_invalid_assignee_without_creating(registered, spy):
    spy.returns["projects.get_members_lite"] = _page(("good", True, 15))
    result = registered["workitem"].fn(action="create", project_id="p", name="example", assignees=["bad"])
    assert result.startswith("Error:") and "bad" in result
    assert spy.recorder.methods == ["projects.get_members_lite"]


def test_empty_assignees_is_explicit_clear_and_skips_member_lookup(registered, spy):
    registered["workitem"].fn(action="update", project_id="p", workitem_id="w", assignees=[])
    assert spy.recorder.methods == ["work_items.update"]


def test_merge_of_valid_users_is_preserved(registered, spy):
    spy.returns["projects.get_members_lite"] = _page(("old", True, 15), ("new", True, 20))
    spy.returns["work_items.retrieve"] = SimpleNamespace(assignees=["old"])
    registered["workitem"].fn(action="manage_assignee", project_id="p", workitem_id="w", add_user_id="new")
    assert spy.recorder.calls[-1].kwargs["data"].assignees == ["old", "new"]


def test_failed_membership_read_refuses_assignee_write(registered, spy):
    from plane.errors.errors import HttpError

    spy.returns["projects.get_members_lite"] = HttpError("missing endpoint", status_code=404)
    result = registered["workitem"].fn(action="update", project_id="p", workitem_id="w", assignees=["x"])
    assert result.startswith("Error:") and "404" in result
    assert spy.recorder.methods == ["projects.get_members_lite"]
