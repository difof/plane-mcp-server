"""v2 Pages should use their own verbs, routes, envelope and collections."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest


@pytest.fixture
def calls(monkeypatch):
    recorded = []
    pages = __import__("plane_mcp.tools.page", fromlist=["page"])
    v2 = __import__("plane_mcp.tools.page_v2", fromlist=["page_v2"])
    monkeypatch.setattr(pages, "get_plane_client_context", lambda: (SimpleNamespace(), "tech"))

    def request(client, slug, method, path, **kwargs):
        recorded.append({"slug": slug, "method": method, "path": path, **kwargs})
        return {"status": 200, "ok": True, "data": {"collection_id": None}}

    monkeypatch.setattr(v2, "request_plane_api", request)
    return recorded


@pytest.mark.parametrize(
    ("args", "expected_method", "expected_path"),
    [
        ({"action": "list"}, "GET", "/api/v2/workspaces/tech/pages/"),
        ({"action": "list", "project_id": "p"}, "GET", "/api/v2/workspaces/tech/projects/p/pages/"),
        ({"action": "retrieve", "page_id": "w"}, "GET", "/api/v2/workspaces/tech/pages/w/"),
        (
            {"action": "create", "name": "Wiki", "description_html": "<p>Hi</p>"},
            "POST",
            "/api/v2/workspaces/tech/pages/",
        ),
        ({"action": "update", "page_id": "w", "name": "New"}, "PATCH", "/api/v2/workspaces/tech/pages/w/"),
        ({"action": "archive", "page_id": "w"}, "POST", "/api/v2/workspaces/tech/pages/w/archive/"),
        ({"action": "archive", "page_id": "w", "archive": False}, "POST", "/api/v2/workspaces/tech/pages/w/unarchive/"),
        (
            {"action": "delete", "project_id": "p", "page_id": "w"},
            "DELETE",
            "/api/v2/workspaces/tech/projects/p/pages/w/",
        ),
        (
            {"action": "list_workitem_pages", "project_id": "p", "workitem_id": "w"},
            "GET",
            "/api/v2/workspaces/tech/projects/p/work-items/w/pages/",
        ),
        (
            {"action": "attach_to_workitem", "project_id": "p", "workitem_id": "w", "page_id": "page"},
            "POST",
            "/api/v2/workspaces/tech/projects/p/work-items/w/pages/",
        ),
        (
            {"action": "detach_from_workitem", "project_id": "p", "workitem_id": "w", "workitem_page_id": "link"},
            "DELETE",
            "/api/v2/workspaces/tech/projects/p/work-items/w/pages/link/",
        ),
    ],
)
def test_page_v2_routes(registered, calls, args, expected_method, expected_path):
    result = registered["page"].fn(api_version="v2", **args)
    assert result["ok"] is True
    assert calls[-1]["method"] == expected_method
    assert calls[-1]["path"] == expected_path


def test_create_page_carries_body_and_parent(registered, calls):
    registered["page"].fn(
        action="create", api_version="v2", name="Doc", description_html="<p>Body</p>", parent_id="parent"
    )
    assert json.loads(calls[0]["body"]) == {"name": "Doc", "description_html": "<p>Body</p>", "parent_id": "parent"}


def test_v2_cursor_pagination_is_explicit(registered, calls):
    registered["page"].fn(action="list", api_version="v2", per_page=20, cursor="next")
    assert json.loads(calls[0]["params"]) == {"per_page": 20, "paginate": "cursor", "cursor": "next"}


def test_setting_collection_uses_v2_add_only_if_page_is_unfiled(registered, calls):
    registered["page"].fn(action="set_collection", api_version="v2", page_id="page", collection_id="new")
    assert [row["method"] for row in calls] == ["GET", "POST"]
    assert calls[1]["path"] == "/api/v2/workspaces/tech/collections/new/pages/"
    assert json.loads(calls[1]["body"]) == {"add": ["page"]}


def test_setting_collection_moves_from_current_collection(registered, calls, monkeypatch):
    v2 = __import__("plane_mcp.tools.page_v2", fromlist=["page_v2"])

    def fake(client, slug, method, path, **kwargs):
        calls.append({"method": method, "path": path, **kwargs})
        return {"status": 200, "ok": True, "data": {"collection_id": "old"}}

    monkeypatch.setattr(v2, "request_plane_api", fake)
    registered["page"].fn(action="set_collection", api_version="v2", page_id="page", collection_id="new")
    assert calls[1]["path"] == "/api/v2/workspaces/tech/collections/old/pages/page/"
    assert calls[1]["method"] == "PATCH"
    assert json.loads(calls[1]["body"]) == {"collection_id": "new"}


def test_setting_collection_does_not_mutate_on_read_failure(registered, calls, monkeypatch):
    v2 = __import__("plane_mcp.tools.page_v2", fromlist=["page_v2"])

    def missing(client, slug, method, path, **kwargs):
        calls.append({"method": method, "path": path})
        return {"status": 404, "ok": False, "data": {"detail": "not found"}}

    monkeypatch.setattr(v2, "request_plane_api", missing)
    response = registered["page"].fn(action="set_collection", api_version="v2", page_id="p", collection_id="c")
    assert response["status"] == 404
    assert len(calls) == 1


@pytest.mark.parametrize(
    "args",
    [
        {"action": "update", "page_id": "p"},
        {"action": "create", "name": "title"},
        {"action": "create", "name": "title", "description_html": "x", "collection_id": "c", "parent_id": "p"},
        {"action": "attach_to_workitem", "project_id": "p", "workitem_id": "w"},
    ],
)
def test_v2_guards_prevent_incomplete_writes(registered, calls, args):
    result = registered["page"].fn(api_version="v2", **args)
    assert isinstance(result, str) and result.startswith("Error:")
    assert calls == []
