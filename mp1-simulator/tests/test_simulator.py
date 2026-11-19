import pandas as pd
import pytest

from src.contract import ZONE_OF, row_to_payload
from src.faults import severity_curve
from src.generator import build_dataset, load_config

CFG = load_config("configs/scenarios.yaml")


@pytest.fixture(scope="module")
def train():
    return build_dataset(CFG, "train")


def test_same_seed_same_data(train):
    again, _ = build_dataset(CFG, "train")
    pd.testing.assert_frame_equal(train[0], again)


def test_different_seed_different_data(train):
    other, _ = build_dataset(CFG, "train", seed=999)
    assert not train[0]["temperature"].equals(other["temperature"])


def test_twelve_machines_three_zones_matching_contract(train):
    data, _ = train
    assert data["machine_id"].nunique() == 12
    assert set(data["zone"]) == {"A", "B", "C"}
    assert all(ZONE_OF[m] == z for m, z in zip(data["machine_id"], data["zone"]))


def test_one_measurement_per_second(train):
    data, _ = train
    m = data[data["machine_id"] == "M01"]
    assert (m["timestamp"].diff().dropna() == pd.Timedelta(seconds=1)).all()


def test_message_ids_are_unique_ulids(train):
    data, _ = train
    assert data["message_id"].is_unique
    assert (data["message_id"].str.len() == 26).all()


def test_healthy_machine_stays_normal(train):
    data, _ = train
    healthy = data[data["machine_id"] == "M01"]          # no fault in train
    assert (healthy["label"] == "NONE").all()
    assert (healthy["state"] == "RUNNING").all()


def test_bearing_wear_raises_vibration(train):
    data, _ = train
    m = data[data["machine_id"] == "M02"]                # BEARING_WEAR
    assert m["vibration"].tail(3600).mean() > 2 * m["vibration"].head(3600).mean()


def test_overload_raises_current_and_lowers_speed(train):
    data, _ = train
    m = data[data["machine_id"] == "M07"]                # ELECTRICAL_OVERLOAD
    assert m["current"].tail(3600).mean() > 1.2 * m["current"].head(3600).mean()
    assert m["speed"].tail(3600).mean() < m["speed"].head(3600).mean()


def test_overheating_raises_temperature_not_current(train):
    data, _ = train
    m = data[data["machine_id"] == "M03"]                # OVERHEATING
    assert m["temperature"].tail(3600).mean() > m["temperature"].head(3600).mean() + 20
    assert abs(m["current"].tail(3600).mean() / m["current"].head(3600).mean() - 1) < 0.1


def test_severity_curve_zero_before_start_and_one_after_end():
    s = severity_curve("BEARING_WEAR", 100, 1.0, start_s=20, duration_s=40)
    assert (s[:21] == 0).all()
    assert s[-1] == 1.0
    assert (s[1:] >= s[:-1]).all()      


def test_events_match_faults(train):
    _, events = train
    assert len(events) == 8
    assert (events["label_start"] >= events["fault_start"]).all()


def test_payloads_follow_contract_and_hide_ground_truth(train):
    data, _ = train
    for _, row in data.sample(300, random_state=0).iterrows():
        msg = row_to_payload(row)
        assert not {"severity", "label", "fault_type", "machine_type"} & msg.keys()