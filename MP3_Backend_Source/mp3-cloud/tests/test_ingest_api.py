"""T7/T11 - Contrat HTTP de l ingestion : auth, multi-status, erreurs indexes."""

import json
from pathlib import Path
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from app.api import ingest as ingest_api
from app.db.session import get_session
from app.main import app
from app.schemas.messages import PredictionResult
from app.services.ingest import IngestReport, validate_batch

CLIENT = TestClient(app)
HEADERS = {"Authorization": "Bearer test-token"}
BAD_HEADERS = {"Authorization": "Bearer wrong-token"}


@pytest.fixture(autouse=True)
def isolated_writer(monkeypatch):
    """Tests du contrat HTTP avec un writer simule ; jamais de connexion a fog_cloud.

    Les ecritures reelles et leur commit sont testes avec --postgres dans une base dediee.
    """
    async def no_database():
        yield None

    async def validate_only(_session, messages):
        return validate_batch(messages)[1]

    writer = AsyncMock(side_effect=validate_only)
    monkeypatch.setattr(ingest_api, "persist_batch", writer)
    app.dependency_overrides[get_session] = no_database
    try:
        yield writer
    finally:
        app.dependency_overrides.pop(get_session, None)


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
    assert response.json()["code"] == "NO_VALID_MESSAGE"
    assert response.json()["rejected"] == 1


def test_duplicate_only_batch_is_207(isolated_writer):
    isolated_writer.side_effect = None
    isolated_writer.return_value = IngestReport(duplicates=1)
    response = CLIENT.post(
        "/api/v1/ingest/batch",
        json={"messages": [_prediction("01ABCDEF0123")]},
        headers=HEADERS,
    )
    assert response.status_code == 207
    assert response.json() == {"accepted": 0, "duplicates": 1, "rejected": 0, "errors": []}


def test_database_error_has_no_success_counts_or_sql_details(isolated_writer):
    isolated_writer.side_effect = OperationalError(
        "private SQL statement", {"secret": "private-value"}, Exception("private DSN")
    )
    response = CLIENT.post(
        "/api/v1/ingest/batch",
        json={"messages": [_prediction("01ABCDEF0123")]},
        headers=HEADERS,
    )
    assert response.status_code == 503
    assert response.json()["status"] == 503
    assert "accepted" not in response.json()
    assert "private" not in response.text


@pytest.mark.parametrize("messages", [[], [{}], [{"kind": "sensor", "payload": []}]])
def test_invalid_envelope_never_calls_writer(isolated_writer, messages):
    response = CLIENT.post(
        "/api/v1/ingest/batch", json={"messages": messages}, headers=HEADERS
    )
    assert response.status_code == 422
    isolated_writer.assert_not_awaited()


def test_valid_fixture_round_trips_through_http_layer():
    fixture_dir = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "valid"
    fixture = fixture_dir / "prediction_ok.json"
    raw = json.loads(fixture.read_text(encoding="utf-8"))
    parsed = PredictionResult.model_validate(raw["payload"])
    assert parsed.model_version



