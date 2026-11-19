"""Baseline detector: static thresholds with persistence.

This is what a plain monitoring system does. It is the reference the ML model
has to beat (Step 5 of the plan).
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from .contract import TYPE_OF
from .generator import build_dataset, load_config
from .machines import PROFILES

# Engineering rules expressed relative to each machine type's nominal values
TEMP_MARGIN_C = 15.0     # alarm if temperature > nominal + 15 degC
VIB_FACTOR = 1.8         # alarm if vibration > 1.8 x nominal
CURRENT_FACTOR = 1.2     # alarm if current > 1.2 x nominal
SPEED_FACTOR = 0.95      # alarm if speed < 0.95 x nominal
PERSISTENCE = 10         # consecutive violating samples (10 s at 1 Hz) before alarming


def thresholds_for(machine_type: str) -> dict[str, float]:
    p = PROFILES[machine_type]
    return {
        "temperature": p.temperature + TEMP_MARGIN_C,
        "vibration": p.vibration * VIB_FACTOR,
        "current": p.current * CURRENT_FACTOR,
        "speed_min": p.speed * SPEED_FACTOR,
    }


def _persistent(violation: pd.Series, n: int) -> pd.Series:
    """True only when the last n samples ALL violated the threshold."""
    return violation.astype(float).rolling(n, min_periods=n).min().eq(1.0)


def detect_batch(df: pd.DataFrame, persistence: int = PERSISTENCE) -> pd.DataFrame:
    """Add baseline_anomaly (bool) and baseline_fault (str) columns."""
    parts = []
    for machine_id, g in df.groupby("machine_id", sort=False):
        g = g.sort_values("timestamp").copy()
        th = thresholds_for(TYPE_OF[machine_id])

        temp = _persistent(g["temperature"] > th["temperature"], persistence)
        vib = _persistent(g["vibration"] > th["vibration"], persistence)
        elec = _persistent((g["current"] > th["current"]) | (g["speed"] < th["speed_min"]),
                           persistence)

        # a threshold rule only knows WHICH sensor tripped, not the true cause
        g["baseline_fault"] = np.select(
            [elec, temp, vib],
            ["ELECTRICAL_OVERLOAD", "OVERHEATING", "BEARING_WEAR"],
            default="NONE")
        g["baseline_anomaly"] = g["baseline_fault"] != "NONE"
        parts.append(g)

    out = pd.concat(parts, ignore_index=True)
    return out.sort_values(["timestamp", "machine_id"]).reset_index(drop=True)


def summarize(data: pd.DataFrame, events: pd.DataFrame) -> None:
    """Quick preview of baseline quality (full evaluation comes in stage 5)."""
    res = detect_batch(data)
    healthy = res[res["severity"] == 0]
    print(f"False-alarm rate on healthy samples: {healthy['baseline_anomaly'].mean():.4%}")
    print(f"{'machine':8}{'true fault':22}{'baseline says':22}{'latency (min)':>14}")
    for _, ev in events.iterrows():
        hits = res[(res["machine_id"] == ev["machine_id"])
                   & (res["timestamp"] >= ev["fault_start"])
                   & res["baseline_anomaly"]]
        if hits.empty:
            print(f"{ev['machine_id']:8}{ev['fault_type']:22}{'MISSED':22}{'-':>14}")
        else:
            lat = (hits["timestamp"].iloc[0] - ev["fault_start"]).total_seconds() / 60
            print(f"{ev['machine_id']:8}{ev['fault_type']:22}"
                  f"{hits['baseline_fault'].iloc[0]:22}{lat:14.1f}")


if __name__ == "__main__":
    cfg = load_config("configs/scenarios.yaml")
    data, events = build_dataset(cfg, "test")
    summarize(data, events)