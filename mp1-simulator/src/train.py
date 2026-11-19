"""Train the hybrid model: IsolationForest (unsupervised) + RandomForest (supervised).

    python -m src.train                  # validate on held-out machines, refit on all, save
    python -m src.train --no-validate    # skip the validation step
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import (classification_report, confusion_matrix,
                             precision_recall_fscore_support)

from .contract import FAULT_TYPES
from .features import FEATURE_COLUMNS, build_features
from .generator import build_dataset, load_config
from .scoring import MODEL_PATH, calibrate_iforest, score

INFO_PATH = MODEL_PATH.with_name("model_info.json")

# Held out for validation: one faulty machine per fault type (a different machine
# type than the training one) + two healthy machines
VAL_MACHINES = ("M09", "M10", "M11", "M04", "M06", "M12")

LABELS = ["NONE", *FAULT_TYPES]
SHORT = {"NONE": "NONE", "BEARING_WEAR": "BEAR", "OVERHEATING": "HEAT",
         "IMBALANCE": "IMBA", "ELECTRICAL_OVERLOAD": "OVLD"}


def fit_models(feats: pd.DataFrame, seed: int, stride: int = 5,
               n_trees: int = 60, version: str = "dev") -> dict:
    """Fit both models on a feature table that contains severity and label columns."""
    # consecutive 1 Hz samples are near duplicates: keep every `stride`-th per machine
    sub = feats[feats.groupby("machine_id").cumcount() % stride == 0]

    # 1) anomaly detector: healthy samples only (severity == 0)
    healthy_sub = sub[sub["severity"] == 0]
    iforest = IsolationForest(n_estimators=100,
                              max_samples=min(256, len(healthy_sub)),
                              random_state=seed)
    iforest.fit(healthy_sub[FEATURE_COLUMNS].to_numpy(dtype=float))

    # 2) fault classifier: all samples, balanced class weights, small trees
    rf = RandomForestClassifier(n_estimators=n_trees, max_depth=10,
                                min_samples_leaf=20,
                                class_weight="balanced_subsample",
                                n_jobs=-1, random_state=seed)
    rf.fit(sub[FEATURE_COLUMNS].to_numpy(dtype=float), sub["label"])

    # 3) calibrate the anomaly score on ALL healthy rows
    healthy_all = feats[feats["severity"] == 0]
    raw = -iforest.score_samples(healthy_all[FEATURE_COLUMNS].to_numpy(dtype=float))

    return {
        "model_version": version,
        "created": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seed": seed,
        "feature_columns": list(FEATURE_COLUMNS),
        "iforest": iforest,
        "iforest_calibration": calibrate_iforest(raw),
        "rf": rf,
    }


def evaluate(bundle: dict, feats: pd.DataFrame, title: str) -> dict:
    """Per-sample metrics. The grey zone (0 < severity < 0.2) is excluded."""
    res = score(bundle, feats)
    truth = feats["label"].to_numpy()
    sev = feats["severity"].to_numpy()

    keep = ~((sev > 0) & (truth == "NONE"))      # drop ambiguous onset samples
    y_true = truth[keep]
    y_pred = res["predicted_fault"].to_numpy()[keep]
    flag = res["anomaly"].to_numpy()[keep]
    is_fault = y_true != "NONE"
    healthy = sev[keep] == 0

    p, r, f1, _ = precision_recall_fscore_support(
        is_fault.astype(int), flag.astype(int), average="binary", zero_division=0)
    far = float(flag[healthy].mean())

    print(f"\n=== {title} ===")
    print(f"Anomaly detection (per sample): precision={p:.3f}  recall={r:.3f}  "
          f"F1={f1:.3f}  false-alarm rate={far:.4%}")
    print("\nFault classification:")
    print(classification_report(y_true, y_pred, labels=LABELS, zero_division=0, digits=3))
    cm = confusion_matrix(y_true, y_pred, labels=LABELS)
    print(pd.DataFrame(cm, index=[f"true {SHORT[l]}" for l in LABELS],
                       columns=[f"pred {SHORT[l]}" for l in LABELS]).to_string())
    return {"precision": float(p), "recall": float(r), "f1": float(f1),
            "false_alarm_rate": far}


def print_importances(bundle: dict, top: int = 10) -> None:
    imp = pd.Series(bundle["rf"].feature_importances_,
                    index=bundle["feature_columns"]).sort_values(ascending=False)
    print(f"\nTop {top} features (RandomForest):")
    print(imp.head(top).round(3).to_string())


def save_bundle(bundle: dict, metrics: dict | None,
                model_path: Path = MODEL_PATH, info_path: Path = INFO_PATH) -> None:
    model_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(bundle, model_path, compress=3)
    info = {
        "model_version": bundle["model_version"],
        "created": bundle["created"],
        "seed": bundle["seed"],
        "n_features": len(bundle["feature_columns"]),
        "iforest_calibration": bundle["iforest_calibration"],
        "validation_on_unseen_machines": metrics,
    }
    info_path.write_text(json.dumps(info, indent=2), encoding="utf-8")
    print(f"\nModel saved: {model_path} ({model_path.stat().st_size / 1e6:.1f} MB), "
          f"version {bundle['model_version']}")


def main() -> None:
    ap = argparse.ArgumentParser(description="Train the MP1 hybrid model")
    ap.add_argument("--config", default="configs/scenarios.yaml")
    ap.add_argument("--no-validate", action="store_true")
    ap.add_argument("--stride", type=int, default=5)
    ap.add_argument("--version", default=None)
    args = ap.parse_args()

    cfg = load_config(args.config)
    seed = cfg["datasets"]["train"]["seed"]
    version = args.version or f"hybrid-{datetime.now(timezone.utc):%Y-%m-%d}"

    print("Generating training data and features ...")
    data, _ = build_dataset(cfg, "train")
    feats = build_features(data)
    print(f"{len(feats)} feature rows, {len(FEATURE_COLUMNS)} features")

    metrics = None
    if not args.no_validate:
        is_val = feats["machine_id"].isin(VAL_MACHINES)
        print(f"Validation fit: {(~is_val).sum()} rows. Held out: {', '.join(VAL_MACHINES)}")
        trial = fit_models(feats[~is_val], seed, args.stride, version=version)
        metrics = evaluate(trial, feats[is_val],
                           "VALIDATION (machines never seen in training)")

    print("\nRefitting on all training machines ...")
    bundle = fit_models(feats, seed, args.stride, version=version)
    print_importances(bundle)
    save_bundle(bundle, metrics)


if __name__ == "__main__":
    main()