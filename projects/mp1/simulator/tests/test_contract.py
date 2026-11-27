import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from src.contract import MachineData

FIXTURES = Path(__file__).resolve().parents[2] / "contracts" / "fixtures"
pytestmark = pytest.mark.skipif(
    not (FIXTURES / "valid" / "sensor_ok.json").exists(),
    reason="contracts/fixtures not present on this branch")

def sensor_ok() -> dict:
    """Fixtures wrap the message as {"kind":..., "payload":...}; MQTT sends only the payload."""
    raw = json.loads((FIXTURES / "valid" / "sensor_ok.json").read_text(encoding="utf-8"))
    assert raw["kind"] == "sensor"
    return raw["payload"]


def test_team_valid_fixture_is_accepted():
    MachineData(**sensor_ok())


@pytest.mark.parametrize("field,value", [
    ("timestamp", "2026-10-30T14:25:31"),    # naive timestamp (cf. invalid/naive_timestamp.json)
    ("machine_id", "M13"),                   # unknown machine (cf. invalid/unknown_machine.json)
    ("zone", "B"),                           # zone inconsistent with M01
    ("temperature", 999),                    # out of range
    ("vibration", -1),
    ("state", "BROKEN"),
])
def test_invalid_values_are_rejected(field, value):
    p = sensor_ok()
    p[field] = value
    with pytest.raises(ValidationError):
        MachineData(**p)


@pytest.mark.parametrize("field", ["message_id", "state", "temperature"])
def test_missing_required_field_is_rejected(field):
    p = sensor_ok()
    del p[field]
    with pytest.raises(ValidationError):
        MachineData(**p)