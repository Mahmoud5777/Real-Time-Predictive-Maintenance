"""Machine profiles and normal-operation signal generation."""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

SQRT3 = 3 ** 0.5
VOLTAGE_V = 400.0
POWER_FACTOR = 0.85
LOAD_NOMINAL = 0.75   # reference load (75 %) at which nominal values apply
GRID_HZ = 50.0


@dataclass(frozen=True)
class MachineProfile:
    """Nominal sensor values of a machine type at nominal load."""
    temperature: float             # degC
    vibration: float               # mm/s RMS
    speed: float                   # rpm
    current: float                 # A
    pressure: float | None = None  # bar (None = no pressure sensor)
    ambient: float = 25.0          # degC


PROFILES: dict[str, MachineProfile] = {
    "motor":      MachineProfile(temperature=65, vibration=2.0, speed=1480, current=12.0),
    "pump":       MachineProfile(temperature=60, vibration=2.5, speed=2900, current=9.0,  pressure=6.0),
    "compressor": MachineProfile(temperature=75, vibration=3.5, speed=1750, current=20.0, pressure=8.0),
    "conveyor":   MachineProfile(temperature=50, vibration=1.5, speed=900,  current=6.0),
}


def power_kw(current: np.ndarray) -> np.ndarray:
    """Three-phase electrical power (kW): sqrt(3) * U * I * cos(phi) / 1000."""
    return SQRT3 * VOLTAGE_V * current * POWER_FACTOR / 1000.0


def simulate_normal(
    profile: MachineProfile,
    n_steps: int,
    dt_s: float,
    rng: np.random.Generator,
    load_period_s: float = 3600.0,
    thermal_tau_s: float = 300.0,
) -> dict[str, np.ndarray]:
    """Healthy sensor signals driven by a load cycle."""
    t = np.arange(n_steps) * dt_s

    # 1) Load cycle: slow sinusoid around 75 %, random phase per machine, small noise
    phase = rng.uniform(0, 2 * np.pi)
    load = LOAD_NOMINAL + 0.15 * np.sin(2 * np.pi * t / load_period_s + phase)
    load += rng.normal(0, 0.01, n_steps)
    load = np.clip(load, 0.3, 1.0)
    rel = load / LOAD_NOMINAL            # 1.0 = nominal load

    # 2) Load-dependent signals (physically coherent)
    speed = profile.speed * (1 - 0.02 * (rel - 1)) + rng.normal(0, 0.003 * profile.speed, n_steps)
    current = profile.current * (0.5 + 0.5 * rel) + rng.normal(0, 0.02 * profile.current, n_steps)
    vibration = profile.vibration * (0.85 + 0.15 * rel) + rng.normal(0, 0.05 * profile.vibration, n_steps)
    vibration = np.clip(vibration, 0, None)

    # 3) Temperature follows the load with thermal inertia (first-order lag)
    target = profile.ambient + (profile.temperature - profile.ambient) * rel
    alpha = dt_s / (thermal_tau_s + dt_s)
    temp = np.empty(n_steps)
    temp[0] = target[0]
    for i in range(1, n_steps):
        temp[i] = temp[i - 1] + alpha * (target[i] - temp[i - 1])
    temperature = temp + rng.normal(0, 0.3, n_steps)

    # 4) Optional pressure (NaN when the machine has no pressure sensor)
    if profile.pressure is None:
        pressure = np.full(n_steps, np.nan)
    else:
        pressure = profile.pressure * (0.95 + 0.05 * rel) + rng.normal(0, 0.02 * profile.pressure, n_steps)

    # 5) Grid frequency: ~50 Hz with tiny noise
    frequency = GRID_HZ + rng.normal(0, 0.05, n_steps)

    return {
        "temperature": temperature,
        "vibration": vibration,
        "speed": speed,
        "current": current,
        "pressure": pressure,
        "frequency": frequency,
    }