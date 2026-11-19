"""Evaluation: threshold baseline vs ML on unseen test seeds -> docs/EVALUATION.md

    python -m src.evaluate
    python -m src.evaluate --seeds 7 11 23 --persistence 5
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from .baseline import detect_batch
from .contract import FAULT_TYPES, row_to_payload
from .features import build_features
from .generator import build_dataset, load_config
from .inference import Predictor
from .scoring import PERSISTENCE, apply_persistence, load_bundle, score

LABELS = ["NONE", *FAULT_TYPES]
SHORT = ["NONE", "BEAR", "HEAT", "IMBA", "OVLD"]
BASE = "Baseline (thresholds)"
ML_RAW = "ML raw"
DOCS = Path("docs")


# --------------------------------------------------------------------- metrics
def sample_metrics(df: pd.DataFrame) -> dict:
    """Per-sample precision/recall/F1 + false alarms. Grey zone (0<severity<0.2) excluded."""
    keep = ~((df["severity"] > 0) & (df["label"] == "NONE"))
    d = df[keep]
    y = (d["label"] != "NONE").to_numpy()
    f = d["anomaly"].to_numpy(dtype=bool)
    tp, fp, fn = int((y & f).sum()), int((~y & f).sum()), int((y & ~f).sum())
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0

    healthy = (d["severity"] == 0).to_numpy()
    far = float(f[healthy].mean()) if healthy.any() else 0.0
    flag = pd.Series(f & healthy, index=d.index)
    prev = flag.groupby(d["machine_id"]).shift(1, fill_value=False).astype(bool)
    episodes = int((flag & ~prev).sum())                    # distinct false-alarm episodes
    machine_days = healthy.sum() / 86400
    return {"precision": prec, "recall": rec, "f1": f1, "false_alarm_rate": far,
            "false_alarms_per_machine_day": episodes / machine_days if machine_days else 0.0}


def detection_latencies(df: pd.DataFrame, events: pd.DataFrame) -> pd.DataFrame:
    """First alarm after fault onset, per injected fault (minutes)."""
    rows = []
    for _, ev in events.iterrows():
        fs = pd.to_datetime(ev["fault_start"], utc=True)
        ls = pd.to_datetime(ev["label_start"], utc=True)
        hit = df[(df["machine_id"] == ev["machine_id"]) & (df["timestamp"] >= fs) & df["anomaly"]]
        if hit.empty:
            rows.append({"machine": ev["machine_id"], "fault": ev["fault_type"], "detected": False,
                         "from_onset_min": np.nan, "from_label_min": np.nan, "type_ok": np.nan})
        else:
            t = hit["timestamp"].iloc[0]
            win = hit[(hit["timestamp"] >= ls) & (hit["timestamp"] <= ls + pd.Timedelta(minutes=5))]
            type_ok = (float(win["predicted_fault"].mode().iloc[0] == ev["fault_type"])
                       if len(win) else np.nan)
            rows.append({"machine": ev["machine_id"], "fault": ev["fault_type"], "detected": True,
                         "from_onset_min": (t - fs).total_seconds() / 60,
                         "from_label_min": (t - ls).total_seconds() / 60,   # <0 = before label
                         "type_ok": type_ok})
    return pd.DataFrame(rows)


def confusion(df: pd.DataFrame) -> np.ndarray:
    keep = ~((df["severity"] > 0) & (df["label"] == "NONE"))
    d = df[keep]
    return confusion_matrix(d["label"], d["predicted_fault"], labels=LABELS)


# ------------------------------------------------------------------- one seed
def _key(df: pd.DataFrame) -> np.ndarray:
    ts = pd.to_datetime(df["timestamp"], utc=True).dt.strftime("%Y-%m-%dT%H:%M:%S")
    return (df["machine_id"] + "|" + ts).to_numpy()


def run_seed(cfg: dict, bundle: dict, seed: int, n: int):
    data, events = build_dataset(cfg, "test", seed=seed)
    feats = build_features(data)
    raw = score(bundle, feats)

    base = feats[["machine_id", "timestamp", "severity", "label"]].copy()
    base["timestamp"] = pd.to_datetime(base["timestamp"], utc=True)

    ml = base.copy()
    for c in ("risk_score", "anomaly", "predicted_fault"):
        ml[c] = raw[c].to_numpy()

    bl = detect_batch(data)                                 # baseline, aligned on same rows
    bl_idx = pd.DataFrame({"anomaly": bl["baseline_anomaly"].to_numpy(dtype=bool),
                           "predicted_fault": bl["baseline_fault"].to_numpy()}, index=_key(bl))
    al = bl_idx.reindex(_key(base))
    bdf = base.copy()
    bdf["anomaly"] = al["anomaly"].astype(object).fillna(False).to_numpy(dtype=bool)
    bdf["predicted_fault"] = al["predicted_fault"].fillna("NONE").to_numpy()

    dets = {BASE: bdf, ML_RAW: ml, f"ML + persistence {n}": apply_persistence(ml, n)}
    return dets, events, data


def benchmark_inference(data: pd.DataFrame) -> dict:
    """Per-message latency of the live Predictor (after warm-up)."""
    p = Predictor()
    msgs = [row_to_payload(r) for _, r in data[data["machine_id"] == "M01"].head(700).iterrows()]
    times = []
    for i, m in enumerate(msgs):
        t0 = time.perf_counter()
        p.predict(m)
        if i >= 300:
            times.append((time.perf_counter() - t0) * 1000)
    return {"p50_ms": float(np.percentile(times, 50)), "p95_ms": float(np.percentile(times, 95)),
            "max_ms": float(np.max(times))}


# ---------------------------------------------------------------------- report
def to_md(df: pd.DataFrame) -> str:
    cols = [df.index.name or ""] + [str(c) for c in df.columns]
    lines = ["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
    for idx, r in df.iterrows():
        lines.append("| " + " | ".join([str(idx)] + [str(v) for v in r]) + " |")
    return "\n".join(lines)


def plot_confusions(cms: dict, names: list[str], path: Path) -> None:
    fig, axes = plt.subplots(1, len(names), figsize=(5 * len(names), 4.6))
    for ax, name in zip(np.atleast_1d(axes), names):
        cm = cms[name]
        norm = cm / np.maximum(cm.sum(axis=1, keepdims=True), 1)
        ax.imshow(norm, vmin=0, vmax=1, cmap="Blues")
        ax.set_xticks(range(5), SHORT)
        ax.set_yticks(range(5), SHORT)
        ax.set_xlabel("predicted")
        ax.set_ylabel("true")
        ax.set_title(name, fontsize=9)
        for i in range(5):
            for j in range(5):
                ax.text(j, i, f"{norm[i, j]:.0%}", ha="center", va="center",
                        color="white" if norm[i, j] > 0.5 else "black", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def plot_latency(pivot: pd.DataFrame, path: Path) -> None:
    ax = pivot.astype(float).plot(kind="bar", figsize=(9, 4.5))
    ax.set_ylabel("median detection latency from fault onset (min)")
    ax.set_title("Detection latency (no bar = missed)")
    ax.set_xlabel("")
    plt.xticks(rotation=15)
    plt.tight_layout()
    plt.savefig(path, dpi=120)
    plt.close()


LIMITS = """\
- **Synthetic data.** Physics is simplified: sinusoidal load, first-order thermal lag, fault
  amplitudes are fixed offsets/factors, faults plateau instead of ending in a failure.
- **One fault per machine**, four fault types, no simultaneous faults, no sensor faults,
  no machine stop/idle states. `MISALIGNMENT` from the contract is not simulated.
- **Test seeds only change noise and load phase.** Test machines/faults are the same six
  scenarios on different machines than training; real-world generalisation is not shown.
- **Warm-up:** 300 s of history per machine before the first prediction.
- **IMBALANCE vs BEARING_WEAR confusion:** both raise vibration; the model separates them
  mainly through the ramp shape and temperature, which is weak early in the fault.
- **Labels:** samples with 0 < severity < 0.2 (barely visible onset) are labelled NONE and
  excluded from per-sample metrics; an early alarm there is not counted as an error.
- **Persistence trade-off:** requiring N consecutive anomalies lowers false alarms but adds
  N seconds of latency.
- Thresholds of the baseline and of the ML alarm (0.5 / 0.8) were set by hand, not optimised.
- **Early alarms:** the ML alarms ~11 min before the label turns faulty. The fault type at that
  point is unreliable, so type accuracy is scored on the 5 min after the label starts.
- **Optimistic scores:** train and test come from the same simulator, so near-perfect F1 shows
  the pipeline works, not that it would hold on real machines.
"""


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/scenarios.yaml")
    ap.add_argument("--seeds", type=int, nargs="+", default=[7, 11, 23, 31, 47])
    ap.add_argument("--persistence", type=int, default=PERSISTENCE)
    a = ap.parse_args()

    cfg = load_config(a.config)
    bundle = load_bundle()
    DOCS.mkdir(exist_ok=True)

    metric_rows, lat_all, cms, order, first_data = [], [], {}, [], None
    for seed in a.seeds:
        print(f"seed {seed} ...")
        dets, events, data = run_seed(cfg, bundle, seed, a.persistence)
        first_data = data if first_data is None else first_data
        order = list(dets)
        for name, df in dets.items():
            metric_rows.append({"seed": seed, "detector": name, **sample_metrics(df)})
            lat = detection_latencies(df, events)
            lat["detector"], lat["seed"] = name, seed
            lat_all.append(lat)
            cms[name] = cms.get(name, 0) + confusion(df)

    M = pd.DataFrame(metric_rows)
    L = pd.concat(lat_all, ignore_index=True)

    def ms(col, pct=False, d=3):
        g = M.groupby("detector")[col]
        k = 100 if pct else 1
        return (g.mean() * k).round(d).astype(str) + " ± " + (g.std() * k).round(d).astype(str)

    summary = pd.DataFrame({
        "precision": ms("precision"), "recall": ms("recall"), "F1": ms("f1"),
        "false-alarm rate (%)": ms("false_alarm_rate", pct=True, d=3),
        "false alarms / machine-day": ms("false_alarms_per_machine_day", d=2),
    }).reindex(order)
    summary.index.name = "detector"

    ls = L.groupby("detector").agg(
        detected=("detected", "mean"), onset=("from_onset_min", "median"),
        label=("from_label_min", "median"), type_ok=("type_ok", "mean")).reindex(order)
    lat_summary = pd.DataFrame({
        "faults detected": (ls["detected"] * 100).round(0).astype(int).astype(str) + " %",
        "median latency from onset (min)": ls["onset"].round(1),
        "median latency from label (min)": ls["label"].round(1),
        "correct fault type at 1st alarm": (ls["type_ok"] * 100).round(0).astype("Int64").astype(str) + " %",
    })
    lat_summary.index.name = "detector"

    pivot = L.pivot_table(index="fault", columns="detector", values="from_onset_min",
                          aggfunc="median", dropna=False).reindex(columns=order)
    pivot_md = pivot.round(1).astype(object).fillna("missed")
    pivot_md.index.name = "fault"

    main_det = order[-1]
    plot_confusions(cms, [order[0], main_det], DOCS / "confusion_matrices.png")
    plot_latency(pivot, DOCS / "latency.png")
    bench = benchmark_inference(first_data)

    cm_md = {n: to_md(pd.DataFrame(cms[n], index=[f"true {s}" for s in SHORT],
                                   columns=[f"pred {s}" for s in SHORT])) for n in (order[0], main_det)}

    report = f"""# MP1 evaluation report

Model `{bundle['model_version']}` trained on seed 42 (train set). Evaluated on the test scenarios
with {len(a.seeds)} unseen seeds {a.seeds}; values are mean ± std over seeds.
Alarm persistence for the ML detector: {a.persistence} consecutive samples (1 Hz).

## 1. Per-sample detection quality
{to_md(summary)}

False-alarm rate = alarms on healthy samples (severity 0) / healthy samples.
False alarms per machine-day = distinct false-alarm episodes per 24 h of healthy operation.

## 2. Detection latency (per injected fault, pooled over seeds)
{to_md(lat_summary)}

Latency from onset = first alarm - physical start of the fault. A negative latency from label means
the alarm came before the fault became clearly visible (early detection).

### Median latency from onset by fault type (min)
{to_md(pivot_md)}

![latency](latency.png)

## 3. Fault classification (confusion matrices, summed over seeds)
### {order[0]}
{cm_md[order[0]]}

### {main_det}
{cm_md[main_det]}

![confusion](confusion_matrices.png)

## 4. Inference speed (live Predictor, one message at a time)
p50 = {bench['p50_ms']:.1f} ms, p95 = {bench['p95_ms']:.1f} ms, max = {bench['max_ms']:.1f} ms per message
(target: local detection < 500 ms). Model size: see `models/model_info.json`.

## 5. Limitations
{LIMITS}
"""
    (DOCS / "EVALUATION.md").write_text(report, encoding="utf-8")
    print("\n" + to_md(summary) + "\n\n" + to_md(lat_summary) + "\n\n" + to_md(pivot_md))
    print(f"\nInference: p50={bench['p50_ms']:.1f} ms  p95={bench['p95_ms']:.1f} ms")
    print(f"Report written to {DOCS / 'EVALUATION.md'}")


if __name__ == "__main__":
    main()