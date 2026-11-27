"""Optional smoke test against the actual MP1 model artifact."""
from datetime import datetime, timedelta, timezone

import pytest


def test_real_mp1_predictor_loads_model_and_warms_up():
    pytest.importorskip("numpy")
    pytest.importorskip("pandas")
    pytest.importorskip("sklearn")
    pytest.importorskip("joblib")

    from fog_nodes.common.mp1_inference import MP1Predictor

    predictor = MP1Predictor()
    start = datetime.now(timezone.utc) - timedelta(seconds=301)
    output = None
    for index in range(300):
        timestamp = (start + timedelta(seconds=index)).isoformat().replace("+00:00", "Z")
        payload = {
            "message_id": f"01J{index:023d}",
            "machine_id": "M01",
            "zone": "A",
            "timestamp": timestamp,
            "temperature": 65.0,
            "vibration": 2.0,
            "speed": 1480.0,
            "current": 12.0,
            "pressure": 6.0,
            "power": 8.3,
            "frequency": 50.0,
            "state": "RUNNING",
        }
        output = predictor.predict(payload)

    assert output is not None
    assert output["machine_id"] == "M01"
    assert output["model_version"]
    assert 0.0 <= output["risk_score"] <= 1.0
    assert output["severity"] in {"NORMAL", "WARNING", "CRITICAL"}
