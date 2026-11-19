"""Visual sanity check of the fault signatures -> docs/signals_train.png"""
from __future__ import annotations

from pathlib import Path

import matplotlib
matplotlib.use("Agg")                       # write a PNG file, no window needed
import matplotlib.pyplot as plt

from .generator import build_dataset, load_config

PANELS = [("M02", "vibration"), ("M03", "temperature"),
          ("M05", "vibration"), ("M07", "current")]


def main() -> None:
    cfg = load_config("configs/scenarios.yaml")
    data, events = build_dataset(cfg, "train")

    fig, axes = plt.subplots(len(PANELS), 1, figsize=(10, 10), sharex=True)
    for ax, (mid, sig) in zip(axes, PANELS):
        g = data[data["machine_id"] == mid]
        ev = events[events["machine_id"] == mid].iloc[0]
        ax.plot(g["timestamp"], g[sig], lw=0.6)
        ax.axvline(ev["fault_start"], color="orange", ls="--", label="fault start")
        ax.axvline(ev["label_start"], color="red", ls="--", label="labelled faulty")
        ax.set_ylabel(f"{mid} {sig}\n({ev['fault_type']})")
        ax.legend(loc="upper left")
    fig.suptitle("Simulated fault signatures (train set)")

    out = Path("docs/signals_train.png")
    out.parent.mkdir(exist_ok=True)
    fig.savefig(out, dpi=120, bbox_inches="tight")
    print(f"saved {out}")


if __name__ == "__main__":
    main()