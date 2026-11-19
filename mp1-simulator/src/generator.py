"""Dataset generation: normal + faulty machines with ground-truth labels."""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from .contract import FAULT_TYPES, ZONE_OF, make_message_id
from .faults import apply_fault, severity_curve
from .machines import PROFILES, power_kw, simulate_normal

SENSOR_COLUMNS = ["temperature", "vibration", "speed", "current",
                  "pressure", "frequency", "power"]
FAULT_STATE_SEVERITY = 0.9   # state becomes FAULT beyond this severity


def load_config(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def generate_dataset(machines: list[dict], faults: list[dict], duration_s: int,
                     dt_s: float, seed: int, start_time: str,
                     label_threshold: float = 0.2) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (data, events).

    data  : one row per machine per timestep, contract fields + ground truth
    events: one row per injected fault (needed for detection latency)
    """
    n = int(duration_s // dt_s)
    timestamps = pd.date_range(pd.Timestamp(start_time), periods=n,
                               freq=pd.Timedelta(seconds=dt_s))
    ts_ms = [int(t.timestamp() * 1000) for t in timestamps]

    # ---- validate the configuration against the contract
    for m in machines:
        if ZONE_OF.get(m["id"]) != m["zone"]:
            raise ValueError(f"{m['id']}: zone {m['zone']} contradicts the contract")
    ids = {m["id"] for m in machines}
    fault_by_machine: dict[str, dict] = {}
    for f in faults:
        if f["machine"] not in ids:
            raise ValueError(f"Fault on unknown machine {f['machine']}")
        if f["type"] not in FAULT_TYPES:
            raise ValueError(f"Unknown fault type {f['type']}")
        if f["machine"] in fault_by_machine:
            raise ValueError(f"Only one fault per machine is supported ({f['machine']})")
        fault_by_machine[f["machine"]] = f

    frames, events = [], []
    for idx, m in enumerate(machines):
        profile = PROFILES[m["type"]]
        rng = np.random.default_rng([seed, idx])    # independent, reproducible stream

        signals = simulate_normal(profile, n, dt_s, rng)
        severity = np.zeros(n)
        fault_type = "NONE"

        f = fault_by_machine.get(m["id"])
        if f is not None:
            fault_type = f["type"]
            severity = severity_curve(fault_type, n, dt_s, f["start_s"], f["duration_s"])
            signals = apply_fault(signals, fault_type, severity, profile)

            start_idx = int(round(f["start_s"] / dt_s))
            above = severity >= label_threshold
            if start_idx >= n or not above.any():
                raise ValueError(f"Fault on {m['id']} does not fit in the simulation window")
            events.append({
                "machine_id": m["id"],
                "fault_type": fault_type,
                "fault_start": timestamps[start_idx],
                "label_start": timestamps[int(np.argmax(above))],
            })

        signals["power"] = power_kw(signals["current"])   # derived after faults

        frames.append(pd.DataFrame({
            "message_id": [make_message_id(m["id"], ms, seed) for ms in ts_ms],
            "machine_id": m["id"],
            "zone": m["zone"],
            "machine_type": m["type"],
            "timestamp": timestamps,
            **signals,
            "state": np.where(severity >= FAULT_STATE_SEVERITY, "FAULT", "RUNNING"),
            # ---- ground truth (never published)
            "severity": severity,
            "fault_type": np.where(severity > 0, fault_type, "NONE"),
            "label": np.where(severity >= label_threshold, fault_type, "NONE"),
        }))

    data = pd.concat(frames, ignore_index=True)
    data = data.sort_values(["timestamp", "machine_id"]).reset_index(drop=True)
    data[SENSOR_COLUMNS] = data[SENSOR_COLUMNS].round(2)
    data["severity"] = data["severity"].round(3)

    events_df = pd.DataFrame(
        events, columns=["machine_id", "fault_type", "fault_start", "label_start"])
    return data, events_df


def build_dataset(cfg: dict, name: str, seed: int | None = None):
    """Generate the dataset called `name` ('train' / 'test') from the config."""
    ds = cfg["datasets"][name]
    return generate_dataset(
        machines=cfg["machines"],
        faults=ds["faults"],
        duration_s=ds["duration_s"],
        dt_s=cfg["sample_interval_s"],
        seed=ds["seed"] if seed is None else seed,
        start_time=cfg["start_time"],
        label_threshold=cfg.get("label_threshold", 0.2),
    )