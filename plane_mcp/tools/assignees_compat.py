"""Prevent Plane silently clearing assignees when a member is invalid.

The self-hosted serializer ignores nonassignable UUIDs but replaces the entire
assignee set anyway. Validate first, before create/update touches the work item.
"""

from __future__ import annotations

from typing import Any

from plane.errors.errors import HttpError
from plane.models.query_params import MemberListQueryParams

ROLE_MEMBER = 15


def validate_assignables(client: Any, slug: str, project_id: str, desired: list[str]) -> str | None:
    """Return a correctable error if any requested UUID is not assignable."""
    if not desired:
        return None  # explicit [] is a deliberate clear
    active: set[str] = set()
    cursor: str | None = None
    for _ in range(20):
        try:
            page = client.projects.get_members_lite(
                workspace_slug=slug,
                project_id=project_id,
                params=MemberListQueryParams(per_page=100, cursor=cursor),
            )
        except HttpError as exc:
            return (
                f"Error: cannot validate project assignees (Plane HTTP {exc.status_code}); "
                "refusing a potentially destructive assignee replacement. No changes were made."
            )
        for member in page.results:
            if getattr(member, "is_active", False) and (getattr(member, "role", 0) or 0) >= ROLE_MEMBER:
                active.add(str(member.id))
        if not page.next_page_results:
            missing = sorted(set(desired) - active)
            if missing:
                return (
                    "Error: requested assignee IDs are not active assignable project members: "
                    + ", ".join(missing)
                    + ". No work-item changes were made. Resolve project members before retrying."
                )
            return None
        cursor = page.next_cursor
        if not cursor:
            break
    return "Error: project member listing was incomplete; refusing to replace existing assignees."
