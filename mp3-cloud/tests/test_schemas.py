"""T4/T11 - Validation du contrat : les cas valides passent, les invalides sont rejetes."""

import pytest
from pydantic import ValidationError

from app.schemas.messages import PredictionResult
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
        ("risk_score", 1.5),                      # hors bornes
        ("machine_id", "M13"),                    # machine inconnue
        ("zone", "D"),                            # zone invalide -> extra field interdit
        ("timestamp", "2026-10-30T14:25:31"),     # naive : doit etre refusee
        ("message_id", "x"),                      # identifiant non exploitable
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
