"""Current Plane v2 page and work-item-page API operations.

Keep v2's PATCH/POST unarchive and offset/cursor response envelope intact;
v1 uses different verbs and result models, so shared SDK dispatch is unsafe.
"""

from __future__ import annotations

import json
from typing import Any

from plane.models.pages import CreatePage, UpdatePage

from plane_mcp.api_gateway import request_plane_api
from plane_mcp.toolkit import missing, needs, opt


def run(
    client: Any,
    slug: str,
    action: str,
    *,
    project_id: str,
    page_id: str,
    workitem_id: str,
    workitem_page_id: str,
    collection_id: str,
    parent_id: str,
    name: str,
    description_html: str,
    access: int | None,
    color: str,
    is_locked: bool | None,
    external_source: str,
    external_id: str,
    archive: bool | None,
    cursor: str,
    per_page: int,
) -> dict[str, Any] | str:
    prefix = f"/api/v2/workspaces/{slug}/"
    pages = prefix + (f"projects/{project_id}/pages/" if project_id else "pages/")

    def request(method: str, path: str, *, data: dict[str, Any] | None = None, params: dict[str, Any] | None = None):
        return request_plane_api(
            client,
            slug,
            method,
            path,
            body=json.dumps(data) if data is not None else "",
            params=json.dumps(params) if params else "",
        )

    if action == "list":
        params: dict[str, Any] = {}
        if per_page:
            params["per_page"] = per_page
        if cursor:
            params.update(paginate="cursor", cursor=cursor)
        return request("GET", pages, params=params)

    if action == "create":
        if error := needs(action, name=name, description_html=description_html):
            return error
        if parent_id and collection_id:
            return "Error: pass parent_id or collection_id, not both."
        if project_id and collection_id:
            return "Error: project pages cannot belong to workspace collections."
        data = CreatePage(
            name=name,
            description_html=description_html,
            access=access,
            color=opt(color),
            is_locked=is_locked,
            parent_id=opt(parent_id),
            collection_id=opt(collection_id),
            external_id=opt(external_id),
            external_source=opt(external_source),
        )
        return request("POST", pages, data=data.model_dump(exclude_none=True, mode="json"))

    if action in ("retrieve", "update", "archive", "delete", "set_collection"):
        if not page_id:
            return missing(action, "page_id")
        path = pages + page_id + "/"
        if action == "retrieve":
            return request("GET", path)
        if action == "update":
            if not (name or description_html):
                return missing(action, "name or description_html")
            data = UpdatePage(name=opt(name), description_html=opt(description_html))
            return request("PATCH", path, data=data.model_dump(exclude_none=True, mode="json"))
        if action == "archive":
            return request("POST", path + ("unarchive/" if archive is False else "archive/"))
        if action == "delete":
            return request("DELETE", path)
        if not collection_id:
            return missing(action, "collection_id")
        if project_id:
            return "Error: only workspace pages can belong to a collection."
        current = request("GET", path)
        if not current["ok"]:
            return current
        detail = current["data"]
        if not isinstance(detail, dict):
            return "Error: cannot resolve page's current collection from response."
        previous = detail.get("collection_id")
        if previous == collection_id:
            return {"status": 200, "ok": True, "data": {"page_id": page_id, "collection_id": collection_id}}
        if previous:
            return request(
                "PATCH", prefix + f"collections/{previous}/pages/{page_id}/", data={"collection_id": collection_id}
            )
        return request("POST", prefix + f"collections/{collection_id}/pages/", data={"add": [page_id]})

    if error := needs(action, project_id=project_id, workitem_id=workitem_id):
        return error
    link_path = prefix + f"projects/{project_id}/work-items/{workitem_id}/pages/"
    if action == "list_workitem_pages":
        return request("GET", link_path)
    if action == "attach_to_workitem":
        if not page_id:
            return missing(action, "page_id")
        return request("POST", link_path, data={"page_id": page_id})
    if not workitem_page_id:
        return missing(action, "workitem_page_id")
    return request("DELETE", link_path + workitem_page_id + "/")
