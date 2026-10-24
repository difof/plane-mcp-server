"""Legacy v1 relations API used by current self-hosted Plane CE."""

from __future__ import annotations

import json
from typing import Any

from plane_mcp.api_gateway import request_plane_api


def legacy_relations(
    client: Any,
    slug: str,
    project_id: str,
    workitem_id: str,
    method: str,
    *,
    relation_type: str = "",
    workitem_ids: list[str] | None = None,
) -> dict[str, Any]:
    """GET grouped relations or POST with the CE-specific `issues` field."""
    path = f"/api/v1/workspaces/{slug}/projects/{project_id}/work-items/{workitem_id}/relations/"
    body = json.dumps({"relation_type": relation_type, "issues": workitem_ids}) if method == "POST" else ""
    return request_plane_api(client, slug, method, path, body=body)
