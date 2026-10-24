"""CE project flags remain readable/writable without the dedicated API."""

from types import SimpleNamespace

import pytest
from plane.errors.errors import HttpError
from plane.models.projects import ProjectFeature

from plane_mcp.tools.project_features_compat import read_features, update_features


def _project():
    return SimpleNamespace(
        module_view=True,
        cycle_view=False,
        issue_views_view=True,
        page_view=True,
        intake_view=False,
        is_issue_type_enabled=False,
    )


def test_missing_features_endpoint_reads_base_project_without_guessing_advanced_features(spy):
    spy.returns["projects.get_features"] = HttpError("no feature route", status_code=404)
    spy.returns["projects.retrieve"] = _project()
    result = read_features(spy, "ws", "p")
    assert result["pages"] is True
    assert result["cycles"] is False
    assert result["complete"] is False
    assert "workflows" in result["unavailable"]
    assert spy.recorder.methods == ["projects.get_features", "projects.retrieve"]


def test_update_features_falls_back_to_base_project_patch(spy):
    spy.returns["projects.update_features"] = HttpError("no feature route", status_code=404)
    spy.returns["projects.retrieve"] = _project()
    update_features(spy, "ws", "p", ProjectFeature(modules=False, cycles=True, pages=False))
    patch = spy.recorder.calls[-1].kwargs["data"].model_dump(exclude_none=True)
    assert patch == {"module_view": False, "cycle_view": True, "page_view": False}
    assert spy.recorder.methods == ["projects.update_features", "projects.retrieve", "projects.update"]


def test_unsupported_advanced_flag_is_explicitly_refused_without_partial_writes(spy):
    spy.returns["projects.update_features"] = HttpError("no feature route", status_code=404)
    spy.returns["projects.retrieve"] = _project()
    result = update_features(spy, "ws", "p", ProjectFeature(modules=True, workflows=True))
    assert result.startswith("Error:") and "workflows" in result
    assert "projects.update" not in spy.recorder.methods


@pytest.mark.parametrize("status", [401, 403, 409, 500])
def test_non_404_error_is_not_silently_retried(status, spy):
    spy.returns["projects.get_features"] = HttpError("other error", status_code=status)
    with pytest.raises(HttpError):
        read_features(spy, "ws", "p")
    assert spy.recorder.methods == ["projects.get_features"]
