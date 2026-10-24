"""Self-hosted CE still serves /relations/ instead of /dependencies/."""

import pytest
from plane.errors.errors import HttpError


def test_list_falls_back_to_existing_ce_route(registered, spy, monkeypatch):
    spy.returns["work_items.dependencies.list"] = HttpError("missing", status_code=404)
    calls = []

    def fake(*args, **kwargs):
        calls.append((args, kwargs))
        return {"ok": True, "status": 200, "data": {"blocking": [], "blocked_by": []}}

    monkeypatch.setattr("plane_mcp.tools.workitem_relation.legacy_relations", fake)
    result = registered["workitem_relation"].fn(action="list", project_id="p", workitem_id="w")
    assert result["source"] == "legacy_relations"
    assert result["dependencies"]["blocking"] == []
    assert calls[0][0][-1] == "GET"
    assert spy.recorder.methods == ["work_items.dependencies.list"]


def test_ce_relation_create_uses_issues_not_workitem_ids(registered, spy, monkeypatch):
    spy.returns["work_items.dependencies.create"] = HttpError("missing", status_code=404)
    requests = []

    def fake(client, slug, method, path, **kwargs):
        requests.append((method, path, kwargs))
        return {"ok": True, "status": 201, "data": []}

    monkeypatch.setattr("plane_mcp.tools.relations_compat.request_plane_api", fake)
    result = registered["workitem_relation"].fn(
        action="create", project_id="p", workitem_id="w", workitem_ids=["target"], relation_type="blocking"
    )
    assert result["status"] == 201
    assert requests[0][1].endswith("/work-items/w/relations/")
    import json

    assert json.loads(requests[0][2]["body"]) == {"relation_type": "blocking", "issues": ["target"]}


def test_no_fallback_for_permission_or_server_errors(registered, spy, monkeypatch):
    spy.returns["work_items.dependencies.list"] = HttpError("Forbidden", status_code=403)
    monkeypatch.setattr("plane_mcp.tools.workitem_relation.legacy_relations", lambda *args, **kwargs: None)
    with pytest.raises(HttpError):
        registered["workitem_relation"].fn(action="list", project_id="p", workitem_id="w")


def test_missing_relation_definitions_does_not_block_builtin_relations(registered, spy):
    spy.returns["work_item_relation_definitions.list"] = HttpError("route not found", status_code=404)
    result = registered["workitem_relation"].fn(action="list_definitions")
    assert "blocking" in result["built_in_dependencies"]
    assert result["custom_available"] is False
    assert result["custom_definitions"] == []
