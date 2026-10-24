"""Adapt v1 project-page writes to the upstream server-side Pages patch.

Older Plane uses PATCH to update Pages, while plane-sdk 0.3.1 sends PUT.
A missing PUT method is safe to retry using the documented PATCH contract.
Nested pages also use `parent` rather than the SDK's `parent_id` field.
"""

from __future__ import annotations

import json
from typing import Any

from plane.errors.errors import HttpError
from plane.models.pages import CreatePage, UpdatePage

from plane_mcp.api_gateway import request_plane_api


def _project_page(client: Any, workspace_slug: str, project_id: str, method: str, suffix: str, payload: dict):
    return request_plane_api(
        client,
        workspace_slug,
        method,
        f"/api/v1/workspaces/{workspace_slug}/projects/{project_id}/pages/{suffix}",
        body=json.dumps(payload),
    )


def create_nested_project_page(client: Any, slug: str, project_id: str, data: CreatePage):
    """Use the v1 backend's `parent` field and report a real HTTP response."""
    payload = data.model_dump(exclude_none=True)
    parent_id = payload.pop("parent_id", None)
    if parent_id:
        payload["parent"] = parent_id
    payload.pop("collection_id", None)  # project pages cannot use workspace collections
    return _project_page(client, slug, project_id, "POST", "", payload)


def update_project_page(client: Any, slug: str, project_id: str, page_id: str, data: UpdatePage):
    """Retry only PUT 405, never mask an actual authorization or server error."""
    try:
        return client.pages.update_project_page(workspace_slug=slug, project_id=project_id, page_id=page_id, data=data)
    except HttpError as exc:
        if exc.status_code != 405:
            raise
        return _project_page(client, slug, project_id, "PATCH", page_id + "/", data.model_dump(exclude_none=True))
