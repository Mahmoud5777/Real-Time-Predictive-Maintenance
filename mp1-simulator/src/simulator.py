"""Command line.

Quick sample (MEETING_WEEK1 deliverable: 60 s of contract-format data):
    python -m src.simulator --machines 12 --duration 60 --out data/samples/
    python -m src.simulator --duration 60 --fault BEARING_WEAR      # M01 degrades

Full train/test datasets (CSV + fault events):
    python -m src.simulator --dataset all
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .contract import FAULT_TYPES, row_to_payload
from .generator import build_dataset, generate_dataset, load_config


def write_samples(data, out: Path, duration_s: int) -> None:
    out.mkdir(parents=True, exist_ok=True)
    batch = []
    for machine_id, group in data.groupby("machine_id"):
        msgs = [row_to_payload(row) for _, row in group.iterrows()]
        path = out / f"sensor_{machine_id}_{duration_s}s.json"
        path.write_text(json.dumps(msgs, indent=2), encoding="utf-8")
        batch += [{"kind": "sensor", "payload": m} for m in msgs]
    # Format of POST /api/v1/ingest/batch (max 5000 messages per request)
    (out / "sensor_batch.json").write_text(json.dumps({"messages": batch}), encoding="utf-8")
    print(f"{len(batch)} messages written in {out} (one file per machine + sensor_batch.json)")
    if len(batch) > 5000:
        print("WARNING: more than 5000 messages: split the batch before POSTing it")


def main() -> None:
    p = argparse.ArgumentParser(description="MP1 machine simulator")
    p.add_argument("--config", default="configs/scenarios.yaml")
    p.add_argument("--dataset", choices=["train", "test", "all"], default=None,
                   help="generate full datasets from the config (CSV)")
    p.add_argument("--machines", type=int, default=12, help="sample mode: number of machines")
    p.add_argument("--duration", type=int, default=60, help="sample mode: seconds")
    p.add_argument("--fault", choices=FAULT_TYPES, default=None,
                   help="sample mode: degrade the first machine over the whole duration")
    p.add_argument("--seed", type=int, default=1, help="sample mode: seed")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    cfg = load_config(args.config)

    if args.dataset:                                   # ---- dataset mode
        out = Path(args.out or "data/generated")
        out.mkdir(parents=True, exist_ok=True)
        names = list(cfg["datasets"]) if args.dataset == "all" else [args.dataset]
        for name in names:
            data, events = build_dataset(cfg, name)
            data.to_csv(out / f"{name}.csv", index=False)
            events.to_csv(out / f"{name}_events.csv", index=False)
            print(f"[{name}] {len(data)} rows, {len(events)} faults -> {out / (name + '.csv')}")
        return

    machines = cfg["machines"][: args.machines]        # ---- sample mode
    faults = []
    if args.fault:
        faults = [{"machine": machines[0]["id"], "type": args.fault,
                   "start_s": 0, "duration_s": args.duration}]
    data, _ = generate_dataset(
        machines=machines, faults=faults, duration_s=args.duration,
        dt_s=cfg["sample_interval_s"], seed=args.seed, start_time=cfg["start_time"],
        label_threshold=cfg.get("label_threshold", 0.2))
    write_samples(data, Path(args.out or "data/samples"), args.duration)


if __name__ == "__main__":
    main()