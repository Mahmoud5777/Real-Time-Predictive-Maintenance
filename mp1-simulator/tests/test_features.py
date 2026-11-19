import numpy as np
import pytest

from src.contract import TYPE_OF
from src.features import (FEATURE_COLUMNS, GROUND_TRUTH, WARMUP, FeatureBuffer,
                          _slope, build_features)
from src.generator import build_dataset, load_config

CFG = load_config("configs/scenarios.yaml")


@pytest.fixture(scope="module")
def train():
    return build_dataset(CFG, "train")[0]


def test_machine_types_match_config():
    for m in CFG["machines"]:
        assert TYPE_OF[m["id"]] == m["type"]


def test_slope_of_a_linear_ramp():
    s = _slope(0.5 * np.arange(100), 20)
    assert np.isnan(s[:19]).all()
    assert np.allclose(s[19:], 0.5)


def test_features_complete_and_no_ground_truth(train):
    f = build_features(train)
    assert not f[FEATURE_COLUMNS].isna().any().any()
    assert not set(GROUND_TRUTH) & set(FEATURE_COLUMNS)     # no label leakage
    per_machine = len(train) // 12
    assert len(f) == 12 * (per_machine - (WARMUP - 1))      # warm-up rows dropped


def test_features_are_causal(train):
    """Changing the future must not change past features."""
    m = train[train["machine_id"] == "M02"].head(1000)
    short = build_features(m.head(800))
    full = build_features(m)
    assert np.allclose(short[FEATURE_COLUMNS].to_numpy(),
                       full[FEATURE_COLUMNS].iloc[: len(short)].to_numpy())


def test_streaming_matches_batch(train):
    """Same numbers in training and in production (no train/serve skew)."""
    m = train[train["machine_id"] == "M03"].head(900).reset_index(drop=True)
    batch_last = build_features(m).iloc[-1][FEATURE_COLUMNS].astype(float).to_numpy()
    buf = FeatureBuffer("M03")
    last = None
    for _, row in m.iterrows():
        last = buf.add(row.to_dict())
    assert np.allclose(last[FEATURE_COLUMNS].astype(float).to_numpy(), batch_last, atol=1e-6)


def test_buffer_warms_up_then_answers():
    buf = FeatureBuffer("M01")
    reading = {"temperature": 65.0, "vibration": 2.0, "speed": 1480.0, "current": 12.0}
    for _ in range(WARMUP - 1):
        assert buf.add(reading) is None
    assert buf.add(reading) is not None


def test_unknown_machine_rejected():
    with pytest.raises(ValueError):
        FeatureBuffer("M99")