"""Regression coverage for responses from older self-hosted Plane APIs."""

import json

from plane import PlaneClient
from plane.models.work_items import WorkItem, WorkItemDetail
from requests import PreparedRequest, Response

from plane_mcp.sdk_compat import _normalize_workitem_response, enable_sdk_compat


def _response(path: str, body: object, status: int = 200) -> Response:
    response = Response()
    response.status_code = status
    response.url = "https://plane.example/api/v1/workspaces/ws/projects/p/" + path
    response._content = json.dumps(body).encode()
    response.headers["Content-Type"] = "application/json"
    response.request = PreparedRequest()
    response.request.prepare(method="GET", url=response.url)
    return response


def test_expanded_estimate_is_preserved_and_sdk_accepts_the_workitem():
    point = {"id": "point-id", "value": "3h", "key": 2, "estimate": "estimate-id"}
    response = _response("work-items/", {"results": [{"estimate_point": point}]})

    normalized = _normalize_workitem_response(response)
    item = WorkItem.model_validate(normalized.json()["results"][0])

    assert item.estimate_point == "point-id"
    assert item.model_dump()["estimate_point_expanded"] == point


def test_single_item_and_many_items_can_be_validated():
    point = {"id": "point-id", "value": "2h"}
    response = _response("work-items/number/", {"estimate_point": point})
    item = WorkItemDetail.model_validate(_normalize_workitem_response(response).json())
    assert item.estimate_point == "point-id"
    assert item.model_dump()["estimate_point_expanded"]["value"] == "2h"


def test_only_workitems_are_modified_and_unknown_shapes_are_not_silently_discarded():
    for path, body, code in [
        ("projects/", {"estimate_point": {"id": "a"}}, 200),
        ("work-items/", {"estimate_point": {"value": "no-id"}}, 200),
        ("work-items/", {"estimate_point": {"id": "a"}}, 404),
    ]:
        response = _response(path, body, code)
        original = response.content
        assert _normalize_workitem_response(response).content == original


def test_client_attaches_compatibility_to_all_sdk_resources():
    client = PlaneClient(base_url="https://plane.example", api_key="test")
    enable_sdk_compat(client)
    for resource in (client.work_items, client.cycles, client.modules, client.milestones):
        assert _normalize_workitem_response in resource.session.hooks["response"]
