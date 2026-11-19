"""Receipt normalization and retention configuration are independent of transport formatting."""

import json
from decimal import Decimal, localcontext
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.config import Settings
from app.services.receipts import canonical, digest

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures" / "valid"


def test_receipt_identity_normalizes_defaults_numeric_scale_and_utc():
    payload = json.loads((FIXTURES / "sensor_ok.json").read_text(encoding="utf-8"))["payload"]
    first = digest("sensor", payload)
    variant = {**payload, "timestamp": "2026-10-30T15:25:31+01:00", "speed": 1480.0}
    assert digest("sensor", variant) == first
    assert digest("sensor", {**payload, "temperature": 72}) != first
    prediction = json.loads((FIXTURES / "prediction_ok.json").read_text(encoding="utf-8"))[
        "payload"
    ]
    assert digest("prediction", {**prediction, "risk_score": Decimal("0.5000")}) == digest(
        "prediction", {**prediction, "risk_score": Decimal("0.5")}
    )
    assert len(first) == 32


def test_numeric_receipts_never_round_using_decimal_context():
    with localcontext() as context:
        context.prec = 3
        assert canonical(Decimal("0.1234567890123456789012345678901")) != canonical(
            Decimal("0.1234567890123456789012345678902")
        )
    assert canonical(-0.0) == canonical(0)


@pytest.mark.parametrize(
    "changes",
    [
        {"retention_batch_size": 0},
        {"retention_interval_seconds": 0},
        {"retention_database_timeout_seconds": 0},
        {"retention_metrics_port": 65536},
    ],
)
def test_retention_configuration_is_bounded(changes):
    with pytest.raises(ValidationError):
        Settings(_env_file=None, **changes)


def test_retention_defaults_to_preview():
    assert Settings(_env_file=None).retention_dry_run is True
