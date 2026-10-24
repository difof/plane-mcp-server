"""Bounded REST escape hatch for documented Plane v1/v2 endpoints.

SDK coverage is incomplete and versions can diverge. Requests use the existing
Plane client's credentials and configured origin; callers cannot choose a host,
change authentication headers, or select another workspace through a URL.
"""

from __future__ import annotations

import base64
import binascii
import json
import re
from typing import Any
from urllib.parse import urlsplit

import requests

_MAX_BYTES = 8 * 1024 * 1024
_PATH = re.compile(r"/api/v[12]/[a-zA-Z0-9._~/-]+/?\Z")
_METHODS = frozenset(("GET", "POST", "PATCH", "PUT", "DELETE"))


def _path_for_workspace(path: str, workspace_slug: str) -> str:
    """Require a concrete API path, with the correct workspace when scoped."""
    if len(path) > 2048 or not _PATH.fullmatch(path) or "//" in path:
        raise ValueError("path must be a concrete /api/v1/ or /api/v2/ path, without queries or encoded segments")
    parts = path.strip("/").split("/")
    if any(part in (".", "..") for part in parts):
        raise ValueError("path traversal is not permitted")
    if len(parts) >= 4 and parts[2] == "workspaces" and parts[3] != workspace_slug:
        raise ValueError("path must refer to the connected workspace")
    if not workspace_slug:
        raise ValueError("connected Plane workspace is not configured")
    return path if path.endswith("/") else path + "/"


def _json_object(raw: str, field: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid JSON object") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be a JSON object")
    return value


def _query_params(raw: str) -> dict[str, Any] | None:
    if not raw:
        return None
    obj = _json_object(raw, "params")
    for key, value in obj.items():
        values = value if isinstance(value, list) else [value]
        if not isinstance(key, str) or not all(v is None or isinstance(v, (str, int, float, bool)) for v in values):
            raise ValueError("params keys must be strings and values must be scalars or lists of scalars")
        obj[key] = (
            [str(v).lower() if isinstance(v, bool) else v for v in values]
            if isinstance(value, list)
            else (str(value).lower() if isinstance(value, bool) else value)
        )
    return obj


def _payload(body: str, file_base64: str, filename: str, file_field: str, form: str) -> dict[str, Any]:
    if body and file_base64:
        raise ValueError("supply body or file_base64, not both")
    if form and not file_base64:
        raise ValueError("form requires file_base64")
    if len(body.encode()) > _MAX_BYTES or len(file_base64) > (_MAX_BYTES * 4 // 3 + 32):
        raise ValueError("request payload exceeds the 8 MiB limit")
    if body:
        try:
            return {"json": json.loads(body)}
        except ValueError as exc:
            raise ValueError("body must be valid JSON") from exc
    if file_base64:
        if not filename or not file_field or not re.fullmatch(r"[a-zA-Z0-9_.-]+", file_field):
            raise ValueError("file uploads require filename and a safe file_field")
        try:
            content = base64.b64decode(file_base64, validate=True)
        except (binascii.Error, ValueError) as exc:
            raise ValueError("file_base64 is not valid base64") from exc
        if len(content) > _MAX_BYTES:
            raise ValueError("decoded file exceeds the 8 MiB limit")
        return {"files": {file_field: (filename, content)}, "data": _json_object(form, "form") if form else {}}
    return {}


def _read_response(response: requests.Response) -> dict[str, Any]:
    content = response.content
    if len(content) > _MAX_BYTES:
        raise ValueError("Plane response exceeds the 8 MiB limit; narrow the query or page size")
    content_type = response.headers.get("Content-Type", "")
    if "json" in content_type.lower() and content:
        try:
            value = response.json()
        except ValueError:
            value = content.decode("utf-8", errors="replace")
    elif not content:
        value = None
    else:
        value = {"content_base64": base64.b64encode(content).decode("ascii"), "content_type": content_type}
    headers = {
        key: response.headers[key]
        for key in ("X-RateLimit-Remaining", "X-RateLimit-Reset", "Retry-After")
        if key in response.headers
    }
    return {"status": response.status_code, "ok": response.ok, "data": value, "headers": headers}


def request_plane_api(
    client: Any,
    workspace_slug: str,
    method: str,
    path: str,
    *,
    params: str = "",
    body: str = "",
    file_base64: str = "",
    filename: str = "",
    file_field: str = "file",
    form: str = "",
) -> dict[str, Any]:
    """Issue one authenticated REST request on the configured Plane origin."""
    method = method.upper()
    if method not in _METHODS:
        raise ValueError("method must be GET, POST, PATCH, PUT or DELETE")
    path = _path_for_workspace(path, workspace_slug)
    if method == "GET" and (body or file_base64):
        raise ValueError("GET requests cannot contain a write payload")
    root = client.config.api_root
    if urlsplit(root).scheme not in ("http", "https") or not urlsplit(root).hostname:
        raise ValueError("Plane API origin is not a valid HTTP(S) URL")
    url = root.rstrip("/") + path
    payload = _payload(body, file_base64, filename, file_field, form)
    headers = {"Accept": "application/json"}
    if client.config.api_key:
        headers["X-Api-Key"] = client.config.api_key
    elif client.config.access_token:
        headers["Authorization"] = f"Bearer {client.config.access_token}"
    else:
        raise ValueError("Plane client is missing authentication")
    if "json" in payload:
        headers["Content-Type"] = "application/json"

    # Stream and cap the response rather than trusting server-supplied length.
    with requests.request(
        method,
        url,
        params=_query_params(params),
        headers=headers,
        timeout=client.config.timeout,
        allow_redirects=False,
        stream=True,
        **payload,
    ) as response:
        chunks = []
        size = 0
        for chunk in response.iter_content(chunk_size=65536):
            size += len(chunk)
            if size > _MAX_BYTES:
                raise ValueError("Plane response exceeds the 8 MiB limit; narrow the query or page size")
            chunks.append(chunk)
        response._content = b"".join(chunks)
        return _read_response(response)
