from fastapi.testclient import TestClient

import api.index as api_module

SNAPSHOT = {
    "meta": {
        "artifact_version": "test-v1",
        "window_start": "2024-08-01",
        "window_end": "2026-07-31",
    },
    "dimensions": {"boroughs": ["Brooklyn"]},
    "signals": [
        {
            "id": "SIG-TEST",
            "type": "volume_surge",
            "severity": "high",
            "as_of": "2026-07-31",
            "district": "Brooklyn 05",
            "borough": "Brooklyn",
            "problem": "Street Condition",
            "agency": None,
            "observed": 80,
            "expected": 20,
            "effect": 4,
            "uncertainty": "Robust baseline",
            "persistence": 1,
            "trigger": "Thresholds passed",
            "evidence": [],
            "data_quality_flags": [],
            "limitation": "Observed pattern only",
            "recommended_action": "Investigate",
            "title": "Volume moved",
            "display_effect": "4.0×",
        }
    ],
    "trends": {"citywide_volume": [], "by_signal": {"SIG-TEST": []}, "by_district": {}, "by_problem": {}},
    "map": [],
    "quality": {},
    "evaluation": {"status": "revalidation_required"},
}


def client(monkeypatch):
    monkeypatch.setattr(api_module, "load_snapshot", lambda: SNAPSHOT)
    return TestClient(api_module.app)


def test_health_and_meta(monkeypatch):
    test_client = client(monkeypatch)
    assert test_client.get("/healthz").json()["artifact"] == "test-v1"
    assert test_client.get("/v1/meta").status_code == 200
    assert test_client.get("/v1/snapshot").json()["meta"]["artifact_version"] == "test-v1"
    assert test_client.get("/v1/evaluation").json()["status"] == "revalidation_required"


def test_signal_filter_and_detail(monkeypatch):
    test_client = client(monkeypatch)
    response = test_client.get("/v1/signals", params={"district": "Brooklyn 05"})
    assert response.status_code == 200
    assert response.json()[0]["id"] == "SIG-TEST"
    assert test_client.get("/v1/signals/SIG-TEST").status_code == 200


def test_unknown_signal_uses_error_envelope(monkeypatch):
    response = client(monkeypatch).get("/v1/signals/UNKNOWN")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "request_error"


def test_api_never_exposes_request_level_fields(monkeypatch):
    response = client(monkeypatch).get("/v1/signals").json()
    serialized = str(response).lower()
    assert "incident_address" not in serialized
    assert "latitude" not in serialized


def test_invalid_filters_and_dates_use_expected_statuses(monkeypatch):
    test_client = client(monkeypatch)
    invalid_limit = test_client.get("/v1/signals", params={"limit": 1000})
    assert invalid_limit.status_code == 422
    assert invalid_limit.json()["error"]["code"] == "validation_error"
    invalid_date = test_client.get("/v1/trends", params={"start_date": "2024-07-31"})
    assert invalid_date.status_code == 422


def test_openapi_contains_every_public_endpoint():
    paths = api_module.app.openapi()["paths"]
    assert {
        "/healthz",
        "/v1/meta",
        "/v1/snapshot",
        "/v1/dimensions",
        "/v1/signals",
        "/v1/signals/{signal_id}",
        "/v1/trends",
        "/v1/map",
        "/v1/quality",
        "/v1/evaluation",
    }.issubset(paths)
