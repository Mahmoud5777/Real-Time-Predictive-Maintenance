"""Fault models: severity curves and their effect on sensor signals."""
from __future__ import annotations

import numpy as np

from .contract import FAULT_TYPES
from .machines import MachineProfile

# Reused in docs/SCENARIOS.md (deliverable: documented failure scenarios)
FAULT_SIGNATURES = {
    "BEARING_WEAR":        "vibration rises exponentially (up to x3.5), temperature +6 degC",
    "OVERHEATING":         "temperature ramps up +30 degC, vibration +10 %, current stable",
    "IMBALANCE":           "vibration up to x3, proportional to speed squared",
    "ELECTRICAL_OVERLOAD": "current +45 %, temperature +15 degC, speed -8 %",
}


def severity_curve(fault_type: str, n_steps: int, dt_s: float,
                   start_s: float, duration_s: float) -> np.ndarray:
    """Severity in [0, 1]: 0 before the fault, 1 once fully developed."""
    t = np.arange(n_steps) * dt_s
    u = np.clip((t - start_s) / duration_s, 0.0, 1.0)      # progress 0 -> 1
    if fault_type == "BEARING_WEAR":
        k = 3.0                                             # slow start, fast end
        return (np.exp(k * u) - 1) / (np.exp(k) - 1)
    return u                                                # linear ramp


def apply_fault(signals: dict[str, np.ndarray], fault_type: str,
                severity: np.ndarray, profile: MachineProfile) -> dict[str, np.ndarray]:
    """Return a copy of the signals modified by the fault."""
    if fault_type not in FAULT_TYPES:
        raise ValueError(f"Unknown fault type: {fault_type}")

    out = {k: v.copy() for k, v in signals.items()}
    s = severity

    if fault_type == "BEARING_WEAR":
        out["vibration"] *= 1 + 2.5 * s
        out["temperature"] += 6 * s
    elif fault_type == "OVERHEATING":
        out["temperature"] += 30 * s
        out["vibration"] *= 1 + 0.1 * s
    elif fault_type == "IMBALANCE":
        ratio = out["speed"] / profile.speed
        out["vibration"] *= 1 + 2.0 * s * ratio ** 2
    elif fault_type == "ELECTRICAL_OVERLOAD":
        out["current"] *= 1 + 0.45 * s
        out["temperature"] += 15 * s
        out["speed"] *= 1 - 0.08 * s
    return out