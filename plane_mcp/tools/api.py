"""Searchable REST coverage for Plane v1/v2, including pages and new endpoints."""

from __future__ import annotations

import json
import re
from functools import lru_cache
from importlib.resources import files
from typing import Any, Literal

from fastmcp import FastMCP

from plane_mcp.api_gateway import request_plane_api
from plane_mcp.client import get_plane_client_context
from plane_mcp.toolkit import Action, build_annotations, build_description, missing

NAME = "api"
TITLE = "Plane REST API"
LEGACY: dict[str, str] = {}
ACTIONS = (
    Action(
        "list",
        optional=("version", "query", "limit", "offset"),
        read=True,
        note="search the documented v1/v2 HTTP method and path catalogue",
    ),
    Action(
        "describe",
        ("path",),
        ("method",),
        read=True,
        note="get matching route templates, names and official docs links",
    ),
    Action(
        "request",
        ("method", "path"),
        ("params", "body", "file_base64", "filename", "file_field", "form"),
        note="call ANY endpoint supported by the configured Plane server, including new v2 APIs; "
        "pass a concrete /api/v1/ or /api/v2/ path. "
        "params, body and form are JSON strings; file_base64 enables multipart uploads. "
        "Writes require explicit user authorization; never use this action for unrequested mutations",
        destructive=True,
    ),
)
FOOTER = (
    "A route listed in the catalogue is documented, NOT guaranteed available on an older self-hosted Plane instance. "
    "The target origin and authenticated workspace are fixed by the MCP connection. "
    "For example, list(query='pages',version='v2') then request(method='GET', "
    "path='/api/v2/workspaces/<connected-slug>/pages/',params='{" + '"limit":10' + "}'). "
    "A failed HTTP call reports its status and body; never assume a missing endpoint succeeded. "
    "Binary downloads return base64 and all responses have an 8 MiB limit."
)


@lru_cache(maxsize=1)
def _catalog() -> dict[str, Any]:
    return json.loads(files("plane_mcp").joinpath("api_catalog.json").read_text(encoding="utf-8"))


def _routes(version: str) -> list[dict[str, str]]:
    catalog = _catalog()["versions"]
    if version == "all":
        return catalog["v1"] + catalog["v2"]
    if version not in catalog:
        raise ValueError("version must be v1, v2 or all")
    return catalog[version]


def _matches_path(template: str, path: str) -> bool:
    pattern = re.sub(r"\\\{[^}]+\\\}", r"[^/]+", re.escape(template))
    return bool(re.fullmatch(pattern, path))


def _list(version: str, query: str, limit: int, offset: int) -> dict[str, Any]:
    if limit < 1 or limit > 100 or offset < 0:
        raise ValueError("limit must be 1-100 and offset must be nonnegative")
    matched = [row for row in _routes(version) if not query or query.lower() in " ".join(row.values()).lower()]
    return {
        "total": len(matched),
        "count": len(matched[offset : offset + limit]),
        "next_offset": offset + limit if offset + limit < len(matched) else None,
        "items": matched[offset : offset + limit],
        "source": _catalog()["source"],
    }


def register(mcp: FastMCP) -> None:
    @mcp.tool(
        name=NAME,
        description=build_description("Plane REST API route catalogue and fallback.", ACTIONS, FOOTER),
        annotations=build_annotations(TITLE, ACTIONS),
    )
    def api(
        action: Literal["list", "describe", "request"],
        version: Literal["", "v1", "v2", "all"] = "",
        query: str = "",
        limit: int = 0,
        offset: int = 0,
        method: str = "",
        path: str = "",
        params: str = "",
        body: str = "",
        file_base64: str = "",
        filename: str = "",
        file_field: str = "",
        form: str = "",
    ) -> dict[str, Any] | str:
        if action == "list":
            return _list(version or "all", query, limit or 30, offset)
        if not path:
            return missing(action, "path")
        if action == "describe":
            matched = [
                row
                for row in _routes(version or "all")
                if _matches_path(row["path"], path) and (not method or row["method"] == method.upper())
            ]
            return {"count": len(matched), "routes": matched, "source": _catalog()["source"]}
        if not method:
            return missing(action, "method")
        client, slug = get_plane_client_context()
        try:
            return request_plane_api(
                client,
                slug,
                method,
                path,
                params=params,
                body=body,
                file_base64=file_base64,
                filename=filename,
                file_field=file_field or "file",
                form=form,
            )
        except ValueError as exc:
            return f"Error: {exc}"
