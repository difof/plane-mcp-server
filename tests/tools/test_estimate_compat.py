"""Older self-hosted Plane instances omit the public estimates endpoint."""

from types import SimpleNamespace

import pytest
from plane.errors.errors import HttpError


def test_retrieve_404_reports_project_estimate_id_without_claiming_the_scale(registered, spy):
    spy.returns["estimates.retrieve"] = HttpError("missing endpoint", status_code=404)
    spy.returns["projects.retrieve"] = SimpleNamespace(estimate="estimate-1")

    response = registered["project_estimate"].fn(action="retrieve", project_id="p")

    assert response["estimate_id"] == "estimate-1"
    assert response["complete"] is False
    assert spy.recorder.methods == ["estimates.retrieve", "projects.retrieve"]


def test_list_points_404_returns_only_seen_values(registered, spy):
    spy.returns["estimates.list_points"] = HttpError("missing endpoint", status_code=404)
    spy.returns["projects.retrieve"] = SimpleNamespace(estimate="estimate-1")
    spy.returns["work_items.list"] = SimpleNamespace(
        results=[
            SimpleNamespace(estimate_point_expanded={"id": "two", "value": "2h", "key": 2, "estimate": "estimate-1"}),
            SimpleNamespace(estimate_point_expanded={"id": "one", "value": "1h", "key": 1, "estimate": "estimate-1"}),
            SimpleNamespace(estimate_point_expanded={"id": "two", "value": "2h", "key": 2}),
            SimpleNamespace(estimate_point_expanded={"id": "unrelated", "value": "x", "estimate": "another"}),
        ],
        next_page_results=False,
    )

    result = registered["project_estimate"].fn(action="list_points", project_id="p", estimate_id="estimate-1")
    assert result["points"] == [{"id": "one", "value": "1h", "key": 1}, {"id": "two", "value": "2h", "key": 2}]
    assert result["complete"] is False
    assert result["source"] == "observed_workitems"
    assert result["scanned_workitems"] == 4
    assert spy.recorder.calls[-1].kwargs["params"].expand == "estimate_point"


def test_non_404_errors_are_not_turned_into_misleading_fallbacks(registered, spy):
    spy.returns["estimates.list_points"] = HttpError("access denied", status_code=403)
    with pytest.raises(HttpError):
        registered["project_estimate"].fn(action="list_points", project_id="p", estimate_id="e")
    assert spy.recorder.methods == ["estimates.list_points"]


def test_unknown_estimate_cannot_be_inferred_from_other_project_work(registered, spy):
    spy.returns["estimates.list_points"] = HttpError("no route", status_code=404)
    spy.returns["projects.retrieve"] = SimpleNamespace(estimate="different")
    result = registered["project_estimate"].fn(action="list_points", project_id="p", estimate_id="e")
    assert "error" in result
    assert "work_items.list" not in spy.recorder.methods


def test_observed_points_follow_pagination_without_assuming_the_first_page_is_all():
    from plane_mcp.tools.project_estimate import _observed_points

    seen_cursors = []

    def list_workitems(*, params, **kwargs):
        seen_cursors.append(params.cursor)
        number = len(seen_cursors)
        return SimpleNamespace(
            results=[
                SimpleNamespace(estimate_point_expanded={"id": str(number), "value": f"{number}h", "key": number})
            ],
            next_page_results=number < 2,
            next_cursor="next" if number < 2 else None,
        )

    client = SimpleNamespace(
        projects=SimpleNamespace(retrieve=lambda **kwargs: SimpleNamespace(estimate="e")),
        work_items=SimpleNamespace(list=list_workitems),
    )
    result = _observed_points(client, "ws", "p", "e")
    assert [point["value"] for point in result["points"]] == ["1h", "2h"]
    assert seen_cursors == [None, "next"]
    assert result["truncated"] is False
    assert result["complete"] is False
