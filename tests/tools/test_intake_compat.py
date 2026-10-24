"""Triage status compatibility on self-hosted Plane."""

import pytest
from plane.errors.errors import HttpError


def test_intake_status_falls_back_only_on_missing_route(registered, spy):
    spy.returns["intake.update_status"] = HttpError("unregistered /status", status_code=404)
    registered["intake"].fn(action="update", project_id="p", workitem_id="w", status=1)
    assert spy.recorder.methods == ["intake.update_status", "intake.update"]
    assert spy.recorder.calls[1].kwargs["data"].status == 1


@pytest.mark.parametrize("status", [400, 401, 403, 409, 500, 503])
def test_intake_status_does_not_retry_real_failures(status, registered, spy):
    spy.returns["intake.update_status"] = HttpError("cannot update", status_code=status)
    with pytest.raises(HttpError):
        registered["intake"].fn(action="update", project_id="p", workitem_id="w", status=1)
    assert spy.recorder.methods == ["intake.update_status"]


def test_intake_source_only_uses_base_endpoint(registered, spy):
    registered["intake"].fn(action="update", project_id="p", workitem_id="w", source="other")
    assert spy.recorder.methods == ["intake.update"]
