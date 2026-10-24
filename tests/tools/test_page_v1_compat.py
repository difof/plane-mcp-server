"""Keep project Pages functional against the v1.4.2 public API patch."""

from types import SimpleNamespace

import pytest
from plane.errors.errors import HttpError
from plane.models.pages import CreatePage, UpdatePage

from plane_mcp.tools.page_v1_compat import create_nested_project_page, update_project_page


def test_v1_update_retries_patch_only_after_method_not_allowed(monkeypatch, spy):
    spy.returns["pages.update_project_page"] = HttpError("PUT unsupported", status_code=405)
    calls = []

    def direct(client, slug, method, path, **kwargs):
        calls.append((slug, method, path, kwargs))
        return {"ok": True, "status": 200, "data": {"name": "Updated"}}

    monkeypatch.setattr("plane_mcp.tools.page_v1_compat.request_plane_api", direct)
    result = update_project_page(spy, "tech", "p", "w", UpdatePage(name="Updated"))
    assert result["ok"] is True
    assert len(spy.recorder.calls) == 1
    assert calls[0][1] == "PATCH"
    assert calls[0][2] == "/api/v1/workspaces/tech/projects/p/pages/w/"
    assert calls[0][3]["body"] == '{"name": "Updated"}'


@pytest.mark.parametrize("status", [401, 403, 404, 409, 500])
def test_v1_update_never_falls_back_when_put_fails_for_other_reason(status, monkeypatch, spy):
    spy.returns["pages.update_project_page"] = HttpError("failure", status_code=status)
    calls = []
    monkeypatch.setattr("plane_mcp.tools.page_v1_compat.request_plane_api", lambda *args, **kwargs: calls.append(True))
    with pytest.raises(HttpError):
        update_project_page(spy, "tech", "p", "w", UpdatePage(name="Updated"))
    assert calls == []


def test_nested_page_uses_parent_field_expected_by_server_patch(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "plane_mcp.tools.page_v1_compat.request_plane_api",
        lambda client, slug, method, path, **kwargs: calls.append((method, path, kwargs)),
    )
    create_nested_project_page(
        SimpleNamespace(), "tech", "p", CreatePage(name="child", description_html="<p>Child</p>", parent_id="parent")
    )
    import json

    payload = json.loads(calls[0][2]["body"])
    assert payload["parent"] == "parent"
    assert "parent_id" not in payload
    assert calls[0][:2] == ("POST", "/api/v1/workspaces/tech/projects/p/pages/")
