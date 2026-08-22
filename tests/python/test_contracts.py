from datetime import datetime

import pytest
from pydantic import ValidationError

from analytics.contracts import ServiceRequest


def request(**overrides):
    payload = {
        "unique_key": "1",
        "created_date": "2026-07-01T10:00:00",
        "closed_date": "2026-07-02T10:00:00",
        "agency": "DOT",
        "complaint_type": "Street Condition",
        "status": "Closed",
        "borough": "BROOKLYN",
        "community_board": "05 BROOKLYN",
        "open_data_channel_type": "ONLINE",
    }
    payload.update(overrides)
    return payload


def test_contract_accepts_privacy_minimized_row():
    parsed = ServiceRequest.model_validate(request(incident_address="not retained"))
    assert parsed.unique_key == "1"
    assert parsed.created_date == datetime(2026, 7, 1, 10)
    assert not hasattr(parsed, "incident_address")


def test_closed_before_created_is_quarantinable_error():
    with pytest.raises(ValidationError, match="closed_date cannot precede"):
        ServiceRequest.model_validate(request(closed_date="2026-06-30T10:00:00"))


def test_unknown_status_is_preserved_for_drift_reporting():
    parsed = ServiceRequest.model_validate(request(status="New Future Status"))
    assert parsed.status == "New Future Status"
