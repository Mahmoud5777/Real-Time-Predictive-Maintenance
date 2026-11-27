"""Preprocessing and feature engineering.

Rules:
- Causal: a feature at time t only uses samples <= t (no future leakage).
- One implementation for batch (training) and streaming (inference).
- Assumes 1 sample/s per machine (contract).
"""
from __future__ import annotations

from collections import deque

import numpy as np
import pandas as pd

from .contract import TYPE_OF
from .machines import PROFILES

SIGNALS = ("temperature", "vibration", "speed", "current")
WINDOWS = (10, 60, 300)            # samples (= seconds at 1 Hz)
WARMUP = max(WINDOWS)              # history needed before the first valid feature row
BUFFER_LEN = 2 * WARMUP            # streaming buffer (long enough for the EWMA to settle)
RATIO_FEATURES = ["vib_over_speed2", "current_over_speed", "temp_over_current"]
GROUND_TRUTH = ("severity", "fault_type", "label")   # never used as features


def _feature_names() -> list[str]:
    names: list[str] = []
    for s in SIGNALS:
        names.append(f"{s}_pu")
        names += [f"{s}_mean_{w}" for w in WINDOWS]
        names += [f"{s}_std_60", f"{s}_std_300",
                  f"{s}_slope_60", f"{s}_slope_300", f"{s}_ewma_60"]
    return names + RATIO_FEATURES


FEATURE_COLUMNS: list[str] = _feature_names()


# ------------------------------------------------------------------ cleaning
def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Sort by time, drop duplicates, fill short sensor dropouts (<= 5 s)."""
    df = df.drop_duplicates(["machine_id", "timestamp"]).copy()
    df = df.sort_values(["machine_id", "timestamp"])
    cols = list(SIGNALS)
    df[cols] = df.groupby("machine_id")[cols].transform(lambda s: s.ffill(limit=5))
    return df.reset_index(drop=True)


# ------------------------------------------------------------------- helpers
def _slope(x: np.ndarray, w: int) -> np.ndarray:
    """Least-squares slope (units per sample) over a trailing window of w samples.

    Implemented as a convolution with a fixed kernel: exact and fast.
    The first w-1 values are NaN.
    """
    out = np.full(len(x), np.nan)
    if len(x) < w:
        return out
    t = np.arange(w) - (w - 1) / 2          # centred time axis
    kernel = t / (t ** 2).sum()             # slope = sum(kernel * x)
    out[w - 1:] = np.convolve(x, kernel[::-1], mode="valid")
    return out


def _machine_features(g: pd.DataFrame, mtype: str) -> pd.DataFrame:
    """Feature table for ONE machine (rows sorted by time)."""
    g = g.reset_index(drop=True)
    p = PROFILES[mtype]

    # per-unit signals: ~1.0 at nominal load for every machine type
    pu = pd.DataFrame({
        "temperature": (g["temperature"] - p.ambient) / (p.temperature - p.ambient),
        "vibration": g["vibration"] / p.vibration,
        "speed": g["speed"] / p.speed,
        "current": g["current"] / p.current,
    })

    feats: dict[str, pd.Series] = {}
    for s in SIGNALS:
        x = pu[s]
        feats[f"{s}_pu"] = x
        for w in WINDOWS:
            feats[f"{s}_mean_{w}"] = x.rolling(w, min_periods=w).mean()
        for w in (60, 300):
            feats[f"{s}_std_{w}"] = x.rolling(w, min_periods=w).std()
            # x60 -> slope expressed in "per minute"
            feats[f"{s}_slope_{w}"] = pd.Series(_slope(x.to_numpy(), w) * 60, index=x.index)
        feats[f"{s}_ewma_60"] = x.ewm(span=60, adjust=False).mean()

    # ratios that expose specific faults
    feats["vib_over_speed2"] = (pu["vibration"] / pu["speed"] ** 2).rolling(60, min_periods=60).mean()
    feats["current_over_speed"] = (pu["current"] / pu["speed"]).rolling(60, min_periods=60).mean()
    feats["temp_over_current"] = (pu["temperature"] / pu["current"]).rolling(60, min_periods=60).mean()

    return pd.DataFrame(feats)[FEATURE_COLUMNS]


# --------------------------------------------------------------------- batch
def build_features(df: pd.DataFrame, drop_warmup: bool = True) -> pd.DataFrame:
    """Features for a whole dataset (training / evaluation).

    Returns machine_id, timestamp, FEATURE_COLUMNS and, if present in the input,
    the ground-truth columns (severity, fault_type, label) for training/scoring.
    """
    df = clean(df)
    parts = []
    for machine_id, g in df.groupby("machine_id", sort=False):
        f = _machine_features(g, TYPE_OF[machine_id])
        f.insert(0, "machine_id", machine_id)
        f.insert(1, "timestamp", g["timestamp"].to_numpy())
        for c in GROUND_TRUTH:
            if c in g.columns:
                f[c] = g[c].to_numpy()
        parts.append(f)

    out = pd.concat(parts, ignore_index=True)
    if drop_warmup:
        out = out.dropna(subset=FEATURE_COLUMNS)
    return out.sort_values(["timestamp", "machine_id"]).reset_index(drop=True)


# ----------------------------------------------------------------- streaming
class FeatureBuffer:
    """Rolling history of ONE machine, for real-time inference."""

    def __init__(self, machine_id: str):
        if machine_id not in TYPE_OF:
            raise ValueError(f"unknown machine_id: {machine_id}")
        self.machine_id = machine_id
        self._rows: deque[dict] = deque(maxlen=BUFFER_LEN)

    def __len__(self) -> int:
        return len(self._rows)

    def add(self, reading: dict) -> pd.Series | None:
        """Add one reading. Returns the feature vector, or None while warming up."""
        self._rows.append({s: float(reading[s]) for s in SIGNALS})
        if len(self._rows) < WARMUP:
            return None
        g = pd.DataFrame(list(self._rows))
        return _machine_features(g, TYPE_OF[self.machine_id]).iloc[-1]