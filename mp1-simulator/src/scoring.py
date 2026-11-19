"""Turn model outputs into the contract's prediction fields.

Shared by training (validation) and inference, so both use the same decision logic.
"""
from __future__ import annotations

from pathlib import Path

import joblib
import numpy as np
import pandas as pd

# Resolved from this file, so it works whatever the caller's working directory is
MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "mp1_model.joblib"

ANOMALY_THRESHOLD = 0.5    # risk_score >= 0.5  -> anomaly = True
CRITICAL_THRESHOLD = 0.8   # risk_score >= 0.8  -> severity CRITICAL (else WARNING)


def sigmoid(z):
    return 1.0 / (1.0 + np.exp(-np.clip(z, -50, 50)))


def calibrate_iforest(healthy_scores: np.ndarray, alarm_quantile: float = 0.999) -> dict:
    """Parameters that map a raw anomaly score to a risk in [0, 1].

    risk = 0.5 at the alarm_quantile of healthy scores, about 0.02 at their median.
    """
    thr = float(np.quantile(healthy_scores, alarm_quantile))
    mid = float(np.median(healthy_scores))
    scale = max((thr - mid) / 4.0, 1e-6)
    return {"threshold": thr, "scale": float(scale)}


def iforest_risk(raw_scores: np.ndarray, calib: dict) -> np.ndarray:
    return sigmoid((raw_scores - calib["threshold"]) / calib["scale"])


def load_bundle(path: str | Path = MODEL_PATH) -> dict:
    bundle = joblib.load(path)
    bundle["rf"].n_jobs = 1     # one row at a time: a thread pool only adds overhead
    return bundle


def score(bundle: dict, X: pd.DataFrame) -> pd.DataFrame:
    """Score feature rows. Returns one row per input row (same index)."""
    A = X[bundle["feature_columns"]].to_numpy(dtype=float)

    # unsupervised part: how unusual is this sample compared with healthy data?
    iso_risk = iforest_risk(-bundle["iforest"].score_samples(A),
                            bundle["iforest_calibration"])

    # supervised part: which fault does it look like?
    proba = bundle["rf"].predict_proba(A)
    classes = list(bundle["rf"].classes_)
    p_fault = 1.0 - proba[:, classes.index("NONE")]
    fault_idx = [i for i, c in enumerate(classes) if c != "NONE"]
    fault_names = np.array([classes[i] for i in fault_idx])
    best_fault = fault_names[proba[:, fault_idx].argmax(axis=1)]

    risk = np.clip(np.maximum(p_fault, iso_risk), 0.0, 1.0)
    anomaly = risk >= ANOMALY_THRESHOLD
    severity = np.select([risk >= CRITICAL_THRESHOLD, anomaly],
                         ["CRITICAL", "WARNING"], default="NORMAL")

    return pd.DataFrame({
        "risk_score": risk,
        "anomaly": anomaly,
        "predicted_fault": np.where(anomaly, best_fault, "NONE"),
        "severity": severity,
        "p_fault": p_fault,        # kept for debugging and evaluation
        "iso_risk": iso_risk,
    }, index=X.index)

# ------------------------------------------------------------ persistence (anti false-alarm)
PERSISTENCE = 30   # consecutive anomalous samples (= 5 s at 1 Hz) required to raise an alarm


def severity_label(risk: np.ndarray, anomaly: np.ndarray) -> np.ndarray:
    return np.select([anomaly & (risk >= CRITICAL_THRESHOLD), anomaly],
                     ["CRITICAL", "WARNING"], default="NORMAL")


def apply_persistence(raw: pd.DataFrame, n: int = PERSISTENCE) -> pd.DataFrame:
    """Confirm an alarm only if the last n samples of that machine were all anomalous.

    raw: columns machine_id, risk_score, anomaly, predicted_fault; time-sorted per machine.
    risk_score becomes the mean of the last n raw risks, capped below the alarm
    threshold while the alarm is unconfirmed (so anomaly=False never has a high risk).
    The streaming Predictor calls this same function, so batch and live agree.
    """
    out = raw.copy()
    g = raw.groupby("machine_id", sort=False)
    mean_risk = g["risk_score"].transform(
        lambda s: s.rolling(n, min_periods=1).mean()).to_numpy(dtype=float)
    confirmed = g["anomaly"].transform(
        lambda s: s.astype(float).rolling(n, min_periods=n).min().eq(1.0)
    ).to_numpy(dtype=bool)
    risk = np.where(confirmed, mean_risk, np.minimum(mean_risk, ANOMALY_THRESHOLD - 0.01))
    out["raw_anomaly"] = raw["anomaly"].to_numpy(dtype=bool)
    out["anomaly"] = confirmed
    out["risk_score"] = np.clip(risk, 0.0, 1.0)
    out["predicted_fault"] = np.where(confirmed, raw["predicted_fault"].to_numpy(), "NONE")
    return out