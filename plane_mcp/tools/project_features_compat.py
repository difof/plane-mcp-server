"""Project feature flags on self-hosted Plane without /features routes."""

from __future__ import annotations

from typing import Any

from plane.errors.errors import HttpError
from plane.models.projects import ProjectFeature, UpdateProject

# Feature flag -> base project field. Keep unsupported flags explicit to avoid
# returning plausible but false successes on older editions.
FLAGS = {
    "modules": "module_view",
    "cycles": "cycle_view",
    "views": "issue_views_view",
    "pages": "page_view",
    "intakes": "intake_view",
    "work_item_types": "is_issue_type_enabled",
}


def read_features(client: Any, workspace_slug: str, project_id: str) -> Any:
    try:
        return client.projects.get_features(workspace_slug=workspace_slug, project_id=project_id)
    except HttpError as exc:
        if exc.status_code != 404:
            raise
    # A nonexistent/inaccessible project still raises 404. A successful base
    # retrieve establishes that this is a missing feature subroute.
    project = client.projects.retrieve(workspace_slug=workspace_slug, project_id=project_id)
    return {
        **{name: getattr(project, attr, None) for name, attr in FLAGS.items()},
        "source": "project_resource",
        "complete": False,
        "unavailable": ["epics", "parallel_cycles", "project_updates", "workflows"],
        "warning": "Only base-project flags are available; this Plane server lacks the /features API.",
    }


def update_features(client: Any, workspace_slug: str, project_id: str, data: ProjectFeature) -> Any:
    try:
        return client.projects.update_features(workspace_slug=workspace_slug, project_id=project_id, data=data)
    except HttpError as exc:
        if exc.status_code != 404:
            raise
    # Before writing, ensure the project exists (avoid masking resource 404).
    client.projects.retrieve(workspace_slug=workspace_slug, project_id=project_id)
    selected = data.model_dump(exclude_none=True)
    unsupported = sorted(set(selected) - set(FLAGS))
    if unsupported:
        return (
            "Error: this Plane server does not expose /features and the base project "
            f"cannot change {', '.join(unsupported)}. No feature changes were applied."
        )
    if not selected:
        return "Error: supply a feature to change; none was provided."
    patch = UpdateProject(**{FLAGS[name]: value for name, value in selected.items()})
    return client.projects.update(workspace_slug=workspace_slug, project_id=project_id, data=patch)
