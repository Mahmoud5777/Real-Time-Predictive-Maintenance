import pandas as pd
import pytest

from src.baseline import PERSISTENCE, detect_batch
from src.generator import build_dataset, load_config

CFG = load_config("configs/scenarios.yaml")


@pytest.fixture(scope="module")
def train_res():
    data, events = build_dataset(CFG, "train")
    return detect_batch(data), events


def make_df(temperatures):
    """Single motor M01, only temperature varies."""
    n = len(temperatures)
    return pd.DataFrame({
        "machine_id": "M01",
        "timestamp": pd.date_range("2026-11-01", periods=n, freq="s", tz="UTC"),
        "temperature": temperatures, "vibration": 2.0, "speed": 1480.0, "current": 12.0,
    })


def test_single_spike_does_not_alarm():
    t = [65.0] * 50
    t[25] = 120.0
    assert not detect_batch(make_df(t))["baseline_anomaly"].any()


def test_sustained_violation_alarms_after_persistence():
    t = [65.0] * 20 + [120.0] * 15 + [65.0] * 5
    res = detect_batch(make_df(t))
    alarms = res.index[res["baseline_anomaly"]]
    assert alarms[0] == 20 + PERSISTENCE - 1
    assert (res.loc[alarms, "baseline_fault"] == "OVERHEATING").all()


def test_no_false_alarms_on_healthy_samples(train_res):
    res, _ = train_res
    assert res[res["severity"] == 0]["baseline_anomaly"].mean() < 0.001


def test_bearing_wear_is_eventually_detected_and_not_before(train_res):
    res, events = train_res
    ev = events[events["machine_id"] == "M02"].iloc[0]
    m = res[res["machine_id"] == "M02"]
    assert not m[m["timestamp"] < ev["fault_start"]]["baseline_anomaly"].any()
    assert m[m["timestamp"] >= ev["fault_start"]]["baseline_anomaly"].any()