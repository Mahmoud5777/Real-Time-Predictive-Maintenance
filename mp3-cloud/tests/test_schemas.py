"""T4/T11 - Validation du contrat : les cas valides passent, les invalides sont rejetes."""

import pytest
from pydantic import ValidationError

from app.schemas.messages import AlertMessage, PredictionResult, TaskEvent
from app.services.ingest import validate_batch

GOOD_PREDICTION = {
    "message_id": "01J9ZK7Q9F3T2W8R1X0YABCDEFG",
    "machine_id": "M01",
    "fog_id": "FOG_A",
    "timestamp": "2026-10-30T14:25:31Z",
    "risk_score": 0.78,
    "anomaly": True,
    "predicted_fault": "BEARING_WEAR",
    "severity": "WARNING",
    "model_version": "iforest-2026-10-28",
}


def test_valid_prediction_is_accepted():
    parsed = PredictionResult.model_validate(GOOD_PREDICTION)
    assert parsed.machine_id == "M01"


@pytest.mark.parametrize(
    "field,value",
    [
        ("risk_score", 1.5),  # hors bornes
        ("machine_id", "M13"),  # machine inconnue
        ("zone", "D"),  # zone invalide -> extra field interdit
        ("timestamp", "2026-10-30T14:25:31"),  # naive : doit etre refusee
        ("message_id", "x"),  # identifiant non exploitable
    ],
)
def test_invalid_payloads_are_rejected(field, value):
    payload = dict(GOOD_PREDICTION)
    if field == "zone":
        payload["zone"] = value
    else:
        payload[field] = value
    with pytest.raises(ValidationError):
        PredictionResult.model_validate(payload)


def test_batch_reports_errors_per_index_without_raising():
    batch = [
        {"kind": "prediction", "payload": GOOD_PREDICTION},
        {"kind": "prediction", "payload": {**GOOD_PREDICTION, "risk_score": 2}},
        {"kind": "nope", "payload": GOOD_PREDICTION},
    ]
    valid, report = validate_batch(batch)
    assert len(valid) == 1
    assert report.accepted == 1 and report.rejected == 2
    assert {e["code"] for e in report.errors} == {"VALIDATION_ERROR", "UNKNOWN_KIND"}


@pytest.mark.parametrize(
    "task_id",
    [
        "b3f1c2d4-6a11-1f3a-9c2e-7d5b1a0e9f42",  # UUIDv1
        "b3f1c2d4-6a11-5f3a-9c2e-7d5b1a0e9f42",  # UUIDv5
        "b3f1c2d4-6a11-4f3a-7c2e-7d5b1a0e9f42",  # variante invalide
    ],
)
def test_task_id_requires_uuid_v4(task_id):
    with pytest.raises(ValidationError):
        TaskEvent.model_validate(_task_payload(task_id))


def _task_payload(task_id: str) -> dict:
    return {
        "message_id": "task-test-0001",
        "task_id": task_id,
        "task_type": "AGGREGATION",
        "priority": "MEDIUM",
        "critical": False,
        "source_fog": "FOG_A",
        "status": "CREATED",
        "created_at": "2026-11-02T08:00:00Z",
    }


def test_task_uuid_v4_uppercase_is_accepted():
    task_id = "B3F1C2D4-6A11-4F3A-9C2E-7D5B1A0E9F42"
    assert TaskEvent.model_validate(_task_payload(task_id)).task_id == task_id


def test_model_version_length_matches_database():
    assert PredictionResult.model_validate({**GOOD_PREDICTION, "model_version": "v" * 64})
    with pytest.raises(ValidationError):
        PredictionResult.model_validate({**GOOD_PREDICTION, "model_version": "v" * 65})


def test_alert_id_length_matches_database():
    payload = {
        "message_id": "alert-test-0001",
        "alert_id": "a" * 64,
        "machine_id": "M01",
        "fog_id": "FOG_A",
        "timestamp": "2026-11-02T08:00:00Z",
        "type": "ANOMALY_DETECTED",
        "severity": "WARNING",
        "message": "Vibration elevee",
    }
    assert AlertMessage.model_validate(payload)
    with pytest.raises(ValidationError):
        AlertMessage.model_validate({**payload, "alert_id": "a" * 65})
