import numpy as np
import pandas as pd
import pytest

from src.contract import row_to_payload
from src.features import WARMUP, build_features
from src.generator import generate_dataset, load_config
from src.inference import Predictor, build_prediction_result
from src.scoring import apply_persistence, score
from src.train import fit_models, save_bundle

CFG = load_config("configs/scenarios.yaml")


@pytest.fixture(scope="module")
def setup(tmp_path_factory):
    faults = [
        {"machine": "M01", "type": "OVERHEATING",         "start_s": 700, "duration_s": 1500},
        {"machine": "M02", "type": "BEARING_WEAR",        "start_s": 700, "duration_s": 1800},
        {"machine": "M03", "type": "IMBALANCE",           "start_s": 700, "duration_s": 1500},
        {"machine": "M04", "type": "ELECTRICAL_OVERLOAD", "start_s": 700, "duration_s": 1500},
    ]
    data, _ = generate_dataset(machines=CFG["machines"][:4], faults=faults, duration_s=3000,
                               dt_s=1, seed=3, start_time=CFG["start_time"])
    model = fit_models(build_features(data), seed=1, stride=2, n_trees=10, version="test")
    path = tmp_path_factory.mktemp("m") / "m.joblib"
    save_bundle(model, None, model_path=path, info_path=path.with_suffix(".json"))
    return data, model, path


def test_warmup_then_valid_outputs(setup):
    data, _, path = setup
    p = Predictor(path)
    m = data[data["machine_id"] == "M01"].head(WARMUP + 5)
    outs = [p.predict(row_to_payload(r)) for _, r in m.iterrows()]
    assert all(not o["anomaly"] and o["risk_score"] == 0 for o in outs[: WARMUP - 1])
    assert not p.warming_up("M01")
    assert all(o["model_version"] == "test" for o in outs)


def test_streaming_matches_batch(setup):
    data, model, path = setup
    m = data[data["machine_id"] == "M02"].head(800)
    p = Predictor(path, persistence=5)
    outs = [p.predict(row_to_payload(r)) for _, r in m.iterrows()][WARMUP - 1:]

    f = build_features(m)
    raw = score(model, f)
    base = pd.concat([f[["machine_id"]], raw[["risk_score", "anomaly", "predicted_fault"]]], axis=1)
    exp = apply_persistence(base, 5)

    assert len(outs) == len(exp)
    assert np.allclose([o["risk_score"] for o in outs], exp["risk_score"], atol=1e-3)
    assert [o["anomaly"] for o in outs] == exp["anomaly"].tolist()


def test_unknown_machine_rejected(setup):
    _, _, path = setup
    with pytest.raises(ValueError):
        Predictor(path).predict({"machine_id": "M99", "timestamp": "2026-11-01T00:00:00Z",
                                 "temperature": 1, "vibration": 1, "speed": 1, "current": 1})


def test_persistence_needs_n_consecutive_samples():
    a = [True, False, True, True, True, True, True]
    raw = pd.DataFrame({"machine_id": "M01", "risk_score": [0.9 if x else 0.1 for x in a],
                        "anomaly": a, "predicted_fault": ["OVERHEATING" if x else "NONE" for x in a]})
    out = apply_persistence(raw, 3)
    assert out["anomaly"].tolist() == [False, False, False, False, True, True, True]
    assert out.loc[~out["anomaly"], "risk_score"].max() < 0.5
    assert out.loc[out["anomaly"], "risk_score"].min() >= 0.5


def test_prediction_result_has_contract_fields(setup):
    out = {"machine_id": "M01", "timestamp": "2026-11-01T00:10:00Z", "risk_score": 0.8,
           "anomaly": True, "predicted_fault": "OVERHEATING", "severity": "CRITICAL",
           "model_version": "x"}
    r = build_prediction_result(out, "FOG_A")
    assert {"message_id", "fog_id", *out} == set(r)
    assert len(r["message_id"]) == 26