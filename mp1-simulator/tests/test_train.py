import numpy as np
import pandas as pd
import pytest

from src.contract import FAULT_TYPES, PredictionOutput
from src.features import FEATURE_COLUMNS, build_features
from src.generator import generate_dataset, load_config
from src.scoring import calibrate_iforest, iforest_risk, load_bundle, score
from src.train import fit_models, save_bundle

CFG = load_config("configs/scenarios.yaml")


@pytest.fixture(scope="module")
def small():
    """4 machines (one per type), one fault each, 50 min: fast to train on."""
    faults = [
        {"machine": "M01", "type": "OVERHEATING",         "start_s": 700, "duration_s": 1500},
        {"machine": "M02", "type": "BEARING_WEAR",        "start_s": 700, "duration_s": 1800},
        {"machine": "M03", "type": "IMBALANCE",           "start_s": 700, "duration_s": 1500},
        {"machine": "M04", "type": "ELECTRICAL_OVERLOAD", "start_s": 700, "duration_s": 1500},
    ]
    data, _ = generate_dataset(machines=CFG["machines"][:4], faults=faults,
                               duration_s=3000, dt_s=1, seed=3,
                               start_time=CFG["start_time"])
    return build_features(data)


@pytest.fixture(scope="module")
def model(small):
    return fit_models(small, seed=1, stride=2, n_trees=10, version="test")


def test_scores_follow_the_contract(model, small):
    res = score(model, small)
    assert res["risk_score"].between(0, 1).all()
    assert set(res["predicted_fault"]) <= {"NONE", *FAULT_TYPES}
    assert set(res["severity"]) <= {"NORMAL", "WARNING", "CRITICAL"}
    assert ((res["predicted_fault"] == "NONE") == ~res["anomaly"]).all()

    row, out = small.iloc[0], res.iloc[0]
    PredictionOutput(machine_id=row["machine_id"],
                     timestamp=row["timestamp"].to_pydatetime(),
                     risk_score=float(out["risk_score"]), anomaly=bool(out["anomaly"]),
                     predicted_fault=out["predicted_fault"], severity=out["severity"],
                     model_version=model["model_version"])


def test_faulty_rows_score_higher_than_healthy(model, small):
    res = score(model, small)
    healthy = res.loc[(small["severity"] == 0).to_numpy(), "risk_score"].mean()
    faulty = res.loc[(small["severity"] >= 0.8).to_numpy(), "risk_score"].mean()
    assert faulty > healthy + 0.3


def test_bundle_uses_exactly_the_feature_list(model):
    assert model["feature_columns"] == FEATURE_COLUMNS
    assert not {"severity", "label", "fault_type"} & set(model["feature_columns"])


def test_training_is_reproducible(model, small):
    again = fit_models(small, seed=1, stride=2, n_trees=10, version="test")
    pd.testing.assert_frame_equal(score(model, small.head(300)),
                                  score(again, small.head(300)))


def test_save_and_load_roundtrip(model, small, tmp_path):
    save_bundle(model, None, model_path=tmp_path / "m.joblib",
                info_path=tmp_path / "info.json")
    loaded = load_bundle(tmp_path / "m.joblib")
    pd.testing.assert_frame_equal(score(model, small.head(200)),
                                  score(loaded, small.head(200)))


def test_iforest_risk_mapping():
    healthy = np.linspace(0.40, 0.50, 1000)
    cal = calibrate_iforest(healthy)
    assert iforest_risk(np.array([cal["threshold"]]), cal)[0] == pytest.approx(0.5)
    assert iforest_risk(np.array([np.median(healthy)]), cal)[0] < 0.05
    r = iforest_risk(np.linspace(0.3, 0.8, 50), cal)
    assert (np.diff(r) >= 0).all() and r.min() >= 0 and r.max() <= 1