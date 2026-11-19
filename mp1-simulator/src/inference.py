"""Inference interface used by MP2 (Fog nodes).

    from src.inference import Predictor
    p = Predictor()
    out = p.predict(sensor_payload)   # contract MachineData dict -> prediction dict

Stateful: one rolling buffer per machine. The first 300 s of a machine return a
neutral result (risk 0, NONE) while the buffer warms up.

CLI:
    python -m src.inference --demo [--machine M01 --rows 6000]
    type messages.jsonl | python -m src.inference --stdin      (one JSON per line)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from collections import deque
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

from .contract import FOG_OF_ZONE, PredictionOutput, format_ts, make_message_id, row_to_payload
from .features import WARMUP, FeatureBuffer
from .scoring import (MODEL_PATH, PERSISTENCE, apply_persistence, load_bundle,
                      score, severity_label)


def _parse_ts(ts) -> datetime:
    if not isinstance(ts, datetime):                       # pandas Timestamp is a datetime
        ts = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
    return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)


class Predictor:
    def __init__(self, model_path: str | Path = MODEL_PATH, persistence: int = PERSISTENCE):
        self.bundle = load_bundle(model_path)
        self.model_version: str = self.bundle["model_version"]
        self.persistence = persistence
        self._buffers: dict[str, FeatureBuffer] = {}
        self._raw: dict[str, deque] = {}

    def warming_up(self, machine_id: str) -> bool:
        b = self._buffers.get(machine_id)
        return b is None or len(b) < WARMUP

    def predict(self, message: dict) -> dict:
        """One sensor message in, one prediction out (contract PredictionOutput fields)."""
        mid = message["machine_id"]
        ts = _parse_ts(message["timestamp"])
        if mid not in self._buffers:
            self._buffers[mid] = FeatureBuffer(mid)        # raises ValueError if unknown
            self._raw[mid] = deque(maxlen=self.persistence)

        feats = self._buffers[mid].add(message)
        if feats is None:                                  # warming up
            return self._out(mid, ts, 0.0, False, "NONE", "NORMAL")

        r = score(self.bundle, feats.astype(float).to_frame().T).iloc[0]
        hist = self._raw[mid]
        hist.append({"machine_id": mid, "risk_score": float(r["risk_score"]),
                     "anomaly": bool(r["anomaly"]), "predicted_fault": str(r["predicted_fault"])})
        res = apply_persistence(pd.DataFrame(list(hist)), self.persistence).iloc[-1]
        risk, anomaly = float(res["risk_score"]), bool(res["anomaly"])
        sev = str(severity_label(np.array([risk]), np.array([anomaly]))[0])
        return self._out(mid, ts, risk, anomaly, str(res["predicted_fault"]), sev)

    def _out(self, mid, ts, risk, anomaly, fault, severity) -> dict:
        out = {"machine_id": mid, "timestamp": format_ts(ts), "risk_score": round(risk, 4),
               "anomaly": anomaly, "predicted_fault": fault, "severity": severity,
               "model_version": self.model_version}
        PredictionOutput(**out)                            # contract check
        return out


def build_prediction_result(out: dict, fog_id: str) -> dict:
    """Prediction dict -> full PredictionResult (DATA_CONTRACT section 2)."""
    ms = int(_parse_ts(out["timestamp"]).timestamp() * 1000)
    return {"message_id": make_message_id(out["machine_id"], ms, f"pred|{fog_id}"),
            "fog_id": fog_id, **out}


# ------------------------------------------------------------------------- CLI
def run_stdin() -> None:
    p = Predictor()
    for line in sys.stdin:
        if line.strip():
            msg = json.loads(line)
            msg = msg.get("payload", msg)                  # accept {"kind","payload"} wrapper
            print(json.dumps(p.predict(msg)), flush=True)


def run_demo(machine: str, rows: int) -> None:
    from .generator import build_dataset, load_config
    cfg = load_config("configs/scenarios.yaml")
    data, events = build_dataset(cfg, "test")
    g = data[data["machine_id"] == machine].head(rows)
    ev = events[events["machine_id"] == machine]
    zone = g["zone"].iloc[0]

    p = Predictor()
    t0 = time.perf_counter()
    results = [p.predict(row_to_payload(r)) for _, r in g.iterrows()]
    ms = (time.perf_counter() - t0) / len(g) * 1000
    print(f"{len(g)} messages, {ms:.1f} ms per prediction (incl. validation)")

    first = next((i for i, r in enumerate(results) if r["anomaly"]), None)
    if ev.empty:
        print(f"{machine} has no injected fault")
    else:
        e = ev.iloc[0]
        print(f"Injected: {e['fault_type']} starting {e['fault_start']} "
              f"(labelled faulty {e['label_start']})")
    if first is None:
        print("No alarm raised in this window (try a larger --rows)")
        return
    r = results[first]
    print(f"First alarm: {r['timestamp']}  {r['predicted_fault']}  "
          f"risk={r['risk_score']}  severity={r['severity']}")

    sample = [build_prediction_result(x, FOG_OF_ZONE[zone]) for x in results[first:first + 60]]
    out = Path("data/samples") / f"predictions_{machine}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(sample, indent=2), encoding="utf-8")
    print(f"{len(sample)} PredictionResult messages saved to {out}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stdin", action="store_true")
    ap.add_argument("--demo", action="store_true")
    ap.add_argument("--machine", default="M01")
    ap.add_argument("--rows", type=int, default=6000)
    a = ap.parse_args()
    if a.stdin:
        run_stdin()
    elif a.demo:
        run_demo(a.machine, a.rows)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()