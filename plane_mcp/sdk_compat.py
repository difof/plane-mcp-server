"""Adapt expanded Plane work-item responses to the pinned SDK's models.

plane-sdk 0.3.1 types ``estimate_point`` as a string even when Plane returns
an expanded object. Normalize only work-item responses *before* SDK Pydantic
validation; keep the expanded object for callers that need the label and key.
"""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from plane.api.base_resource import BaseResource
from requests import Response


def _normalize_estimates(value: Any) -> int:
    """Replace expanded estimate points with IDs, preserving the details."""
    if isinstance(value, list):
        return sum(_normalize_estimates(item) for item in value)
    if not isinstance(value, dict):
        return 0

    changed = 0
    for key, item in list(value.items()):
        if key == "estimate_point" and isinstance(item, dict) and isinstance(item.get("id"), str):
            value["estimate_point_expanded"] = item
            value[key] = item["id"]
            changed += 1
        else:
            changed += _normalize_estimates(item)
    return changed


def _normalize_workitem_response(response: Response, *args: Any, **kwargs: Any) -> Response:
    """Requests response hook. No extra requests or outgoing payload changes."""
    if not response.ok or "work-items" not in urlsplit(response.url).path:
        return response
    if b'"estimate_point"' not in response.content:
        return response
    try:
        body = response.json()
    except ValueError:
        return response
    if _normalize_estimates(body):
        response._content = json.dumps(body, ensure_ascii=False).encode("utf-8")
        response.headers.pop("Content-Length", None)
    return response


def enable_sdk_compat(client: Any) -> None:
    """Attach to this client's SDK resources, not global requests or models."""
    for resource in vars(client).values():
        if isinstance(resource, BaseResource):
            resource.session.hooks["response"].append(_normalize_workitem_response)
