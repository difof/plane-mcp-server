"""Published API inventory and a same-origin, same-workspace REST fallback."""

from __future__ import annotations

import base64
import json
from io import BytesIO
from types import SimpleNamespace

import pytest
from requests import Response

from plane_mcp.api_gateway import request_plane_api
from plane_mcp.tools.api import _catalog


@pytest.fixture
def client():
    return SimpleNamespace(
        config=SimpleNamespace(
            api_root="https://plane.example/proxy",
            api_key="private-test-key",
            access_token=None,
            timeout=7,
        )
    )


@pytest.fixture
def fetch(monkeypatch):
    calls = []

    def request(method, url, **kwargs):
        calls.append((method, url, kwargs))
        response = Response()
        response.status_code = 200
        response._content = b'{"data":[{"id":"one"}],"next_cursor":"next"}'
        response.raw = BytesIO(response._content)
        response._content = False
        response.headers["Content-Type"] = "application/json"
        response.headers["X-RateLimit-Remaining"] = "42"
        return response

    monkeypatch.setattr("plane_mcp.api_gateway.requests.request", request)
    return calls


def test_catalog_is_substantial_and_contains_both_page_scopes(registered):
    v1, v2 = _catalog()["versions"].values()
    assert len(v1) >= 230
    assert len(v2) >= 540
    for version in ("v1", "v2"):
        records = _catalog()["versions"][version]
        paths = {(row["method"], row["path"]) for row in records}
        assert len(records) == len(paths)
        workspace = "{slug}" if version == "v2" else "{workspace_slug}"
        assert ("GET", f"/api/{version}/workspaces/{workspace}/pages/") in paths
        assert ("GET", f"/api/{version}/workspaces/{workspace}/projects/{{project_id}}/pages/") in paths
        assert ("POST", f"/api/{version}/workspaces/{workspace}/projects/{{project_id}}/pages/") in paths
    assert any("recurring" in row["path"] for row in v2)
    assert any("bulk" in row["path"] for row in v2)


def test_search_and_describe_support_versions_and_concrete_paths(registered):
    api = registered["api"].fn
    listing = api(action="list", version="v2", query="pages", limit=5)
    assert listing["total"] > 20
    assert listing["count"] == 5
    assert listing["next_offset"] == 5
    assert all(row["path"].startswith("/api/v2/") for row in listing["items"])

    result = api(action="describe", version="v2", method="GET", path="/api/v2/workspaces/tech/pages/")
    assert result["count"] >= 1
    assert all(r["method"] == "GET" for r in result["routes"])
    assert result["routes"][0]["url"].startswith("https://developers.plane.so/")


def test_authenticated_request_remains_on_configured_origin_and_workspace(client, fetch):
    result = request_plane_api(client, "tech", "GET", "/api/v2/workspaces/tech/pages", params='{"limit":10}')
    assert result["ok"] is True
    assert result["status"] == 200
    assert result["data"]["data"] == [{"id": "one"}]
    assert result["headers"]["X-RateLimit-Remaining"] == "42"
    method, url, kwargs = fetch[0]
    assert (method, url) == ("GET", "https://plane.example/proxy/api/v2/workspaces/tech/pages/")
    assert kwargs["headers"]["X-Api-Key"] == "private-test-key"
    assert kwargs["allow_redirects"] is False
    assert kwargs["timeout"] == 7
    assert kwargs["params"] == {"limit": 10}


@pytest.mark.parametrize(
    "path",
    [
        "https://evil.example/api/v2/workspaces/tech/pages/",
        "//evil.example/api/v2/workspaces/tech/pages/",
        "/api/v2/workspaces/other/pages/",
        "/api/v1/workspaces/other/projects/p/",
        "/api/v2/workspaces/tech/../other/",
        "/api/v2/workspaces/tech/%2e%2e/",
        "/api/v2/workspaces/tech/\\evil",
        "/api/v2/workspaces/tech//pages/",
        "/api/v2/workspaces/tech/pages/?limit=50",
        "/api/v3/workspaces/tech/pages/",
    ],
)
def test_api_path_cannot_escape_origin_version_or_workspace(client, fetch, path):
    with pytest.raises(ValueError):
        request_plane_api(client, "tech", "GET", path)
    assert not fetch


def test_json_body_and_false_query_params_round_trip(client, fetch):
    result = request_plane_api(
        client,
        "tech",
        "PATCH",
        "/api/v2/workspaces/tech/pages/id/",
        body='{"name":"Changed"}',
        params='{"archived":false,"limit":5,"tags":["one","two"]}',
    )
    assert result["ok"]
    method, _, kwargs = fetch[0]
    assert method == "PATCH"
    assert kwargs["json"] == {"name": "Changed"}
    assert kwargs["params"] == {"archived": "false", "limit": 5, "tags": ["one", "two"]}


def test_binary_upload_is_multipart_and_binary_download_is_base64(client, fetch, monkeypatch):
    payload = base64.b64encode(b"abc").decode()
    request_plane_api(
        client,
        "tech",
        "POST",
        "/api/v2/workspaces/tech/pages/id/attachments/",
        file_base64=payload,
        filename="test.txt",
        file_field="file",
        form='{"name":"test"}',
    )
    assert fetch[0][2]["files"] == {"file": ("test.txt", b"abc")}
    assert fetch[0][2]["data"] == {"name": "test"}

    response = Response()
    response.status_code = 200
    response._content = b"binary-content"
    response.raw = BytesIO(response._content)
    response._content = False
    response.headers["Content-Type"] = "application/octet-stream"
    monkeypatch.setattr("plane_mcp.api_gateway.requests.request", lambda *args, **kwargs: response)
    data = request_plane_api(client, "tech", "GET", "/api/v2/workspaces/tech/pages/id/attachments/a/download/")
    assert base64.b64decode(data["data"]["content_base64"]) == b"binary-content"


def test_refuses_bad_payloads_and_get_writes(client, fetch):
    for kwargs in [
        {"method": "GET", "body": "{}"},
        {"method": "POST", "body": "not-json"},
        {"method": "POST", "params": '["not-a-dict"]'},
        {"method": "POST", "file_base64": "invalid-base64", "filename": "a"},
        {"method": "POST", "body": "{}", "file_base64": "YWJj"},
        {"method": "POST", "form": "{}"},
    ]:
        method = kwargs.pop("method")
        with pytest.raises(ValueError):
            request_plane_api(client, "tech", method, "/api/v2/workspaces/tech/pages/", **kwargs)
    assert not fetch


def test_gateway_supports_unknown_future_routes_without_catalog_update(client, fetch):
    result = request_plane_api(client, "tech", "GET", "/api/v2/workspaces/tech/new-feature/")
    assert result["ok"]
    assert len(fetch) == 1


def test_api_request_tool_uses_credential_context_and_preserves_error_status(registered, client, monkeypatch):
    module = __import__("plane_mcp.tools.api", fromlist=["api"])
    monkeypatch.setattr(module, "get_plane_client_context", lambda: (client, "tech"))
    response = Response()
    response.status_code = 404
    response._content = json.dumps({"detail": "endpoint missing"}).encode()
    response.raw = BytesIO(response._content)
    response._content = False
    response.headers["Content-Type"] = "application/problem+json"
    monkeypatch.setattr("plane_mcp.api_gateway.requests.request", lambda *args, **kwargs: response)
    result = registered["api"].fn(action="request", method="GET", path="/api/v2/workspaces/tech/pages/")
    assert result["ok"] is False
    assert result["status"] == 404
    assert result["data"]["detail"] == "endpoint missing"
