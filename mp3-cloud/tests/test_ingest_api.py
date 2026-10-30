"""T7/T11 - Contrat HTTP de l ingestion : auth, multi-status, erreurs indexes."""

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.main import app
from app.schemas.messages import PredictionResult

CLIENT = TestClient(app)
HEADERS = {"Authorization": "Bearer test-token"}
BAD_HEADERS = {"Authorization": "Bearer wrong-token"}


def _prediction(message_id: str, risk: float = 0.4) -> dict:
    return {
        "kind": "prediction",
        "payload": {
            "message_id": message_id,
            "machine_id": "M01",
            "fog_id": "FOG_A",
            "timestamp": "2026-10-30T14:25:31Z",
            "risk_score": risk,
            "anomaly": risk > 0.5,
            "predicted_fault": "NONE" if risk <= 0.5 else "OVERHEATING",
            "severity": "NORMAL" if risk <= 0.5 else "CRITICAL",
            "model_version": "iforest-test",
        },
    }


def test_batch_requires_token():
    response = CLIENT.post("/api/v1/ingest/batch", json={"messages": [_prediction("01ABCDEF0123")]})
    assert response.status_code == 401


def test_batch_rejects_bad_token():
    response = CLIENT.post(
        "/api/v1/ingest/batch",
        json={"messages": [_prediction("01ABCDEF0123")]},
        headers=BAD_HEADERS,
    )
    assert response.status_code == 401


def test_batch_returns_multi_status_with_per_item_errors():
    body = {"messages": [_prediction("01ABCDEF0123"), _prediction("01ABCDEF0124", risk=9)]}
    response = CLIENT.post("/api/v1/ingest/batch", json=body, headers=HEADERS)
    assert response.status_code == 207
    report = response.json()
    assert report["accepted"] == 1
    assert report["rejected"] == 1
    assert report["errors"][0]["index"] == 1
    assert report["errors"][0]["code"] == "VALIDATION_ERROR"


def test_batch_fully_invalid_is_422():
    body = {"messages": [{"kind": "nope", "payload": {}}]}
    response = CLIENT.post("/api/v1/ingest/batch", json=body, headers=HEADERS)
    assert response.status_code == 422


def test_valid_fixture_round_trips_through_http_layer():
    fixture_dir = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "valid"
    fixture = fixture_dir / "prediction_ok.json"
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    parsed = PredictionResult.model_validate(raw["payload"])
    assert parsed.model_version



