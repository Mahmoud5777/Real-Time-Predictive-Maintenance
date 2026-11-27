"""Shared data contract (docs/DATA_CONTRACT.md) expressed as code.

Single source of truth for MP1: constants, validation models, message ids.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from typing import Literal, Optional

import pandas as pd
from pydantic import BaseModel, Field, field_validator, model_validator

# ----------------------------------------------------------------- constants
MACHINE_IDS: list[str] = [f"M{i:02d}" for i in range(1, 13)]           # M01..M12
ZONES = ("A", "B", "C")
ZONE_OF: dict[str, str] = {m: ZONES[i // 4] for i, m in enumerate(MACHINE_IDS)}
FOG_OF_ZONE = {z: f"FOG_{z}" for z in ZONES}
MACHINE_TYPES = ("motor", "pump", "compressor", "conveyor")
TYPE_OF: dict[str, str] = {m: MACHINE_TYPES[i % 4] for i, m in enumerate(MACHINE_IDS)}

FAULT_TYPES = ("BEARING_WEAR", "OVERHEATING", "IMBALANCE", "ELECTRICAL_OVERLOAD")

OPTIONAL_FIELDS = ("pressure", "power", "frequency")

# ------------------------------------------------------------------ message id
_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def make_message_id(machine_id: str, ts_ms: int, salt: str | int = "") -> str:
    """Deterministic ULID-format id (26 chars, Crockford base32).

    48 bits of timestamp (ms) + 80 bits derived from a hash of (salt, machine, time).
    Same inputs -> same id: reproducible datasets and Cloud-side deduplication.
    """
    digest = hashlib.sha256(f"{salt}|{machine_id}|{ts_ms}".encode()).digest()
    value = (ts_ms << 80) | int.from_bytes(digest[:10], "big")
    chars = []
    for _ in range(26):
        chars.append(_CROCKFORD[value & 31])
        value >>= 5
    return "".join(reversed(chars))


def format_ts(ts: datetime) -> str:
    """ISO-8601 UTC with 'Z' suffix, as required by the contract."""
    return ts.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ------------------------------------------------------------ MachineData (MP1 -> MP2)
class MachineData(BaseModel):
    """Payload published on fog/{zone}/sensor/{machine_id} (contract section 1)."""
    message_id: str = Field(min_length=26, max_length=36)
    machine_id: str
    zone: Literal["A", "B", "C"]
    timestamp: datetime
    temperature: float = Field(ge=-50, le=300)
    vibration: float = Field(ge=0, le=100)
    speed: float = Field(ge=0, le=20000)
    current: float = Field(ge=0, le=1000)
    pressure: Optional[float] = Field(default=None, ge=0, le=100)
    power: Optional[float] = Field(default=None, ge=0, le=1000)
    frequency: Optional[float] = Field(default=None, ge=0, le=400)
    state: Literal["RUNNING", "IDLE", "STOPPED", "FAULT"]

    @field_validator("machine_id")
    @classmethod
    def _known_machine(cls, v: str) -> str:
        if v not in ZONE_OF:
            raise ValueError(f"unknown machine_id: {v}")
        return v

    @field_validator("timestamp")
    @classmethod
    def _utc_and_sane(cls, v: datetime) -> datetime:
        if v.tzinfo is None or v.utcoffset() != timedelta(0):
            raise ValueError("timestamp must be UTC with a 'Z' suffix")
        if v.year < 2020:
            raise ValueError("timestamp must be >= 2020")
        if v > datetime.now(timezone.utc) + timedelta(seconds=5):
            raise ValueError("timestamp must not be in the future")
        return v

    @model_validator(mode="after")
    def _zone_matches_machine(self) -> "MachineData":
        if ZONE_OF[self.machine_id] != self.zone:
            raise ValueError(f"zone {self.zone} does not match {self.machine_id}")
        return self


# ------------------------------------------- PredictionOutput (what MP1's ML returns)
class PredictionOutput(BaseModel):
    """What predict() returns. MP2 adds message_id and fog_id before publishing
    the full PredictionResult on fog/{fog_id}/predictions."""
    machine_id: str
    timestamp: datetime
    risk_score: float = Field(ge=0, le=1)
    anomaly: bool
    predicted_fault: Literal["NONE", "BEARING_WEAR", "OVERHEATING", "IMBALANCE",
                             "ELECTRICAL_OVERLOAD", "MISALIGNMENT"]
    severity: Literal["NORMAL", "WARNING", "CRITICAL"]
    model_version: str


# ------------------------------------------------------------------- converters
def row_to_payload(row: pd.Series, timestamp: datetime | None = None,
                   message_id: str | None = None) -> dict:
    """Dataset row -> validated contract payload.

    Only contract fields are copied: ground-truth columns (severity, label, ...)
    never leave the simulator.
    """
    ts = timestamp if timestamp is not None else row["timestamp"]
    payload = {
        "message_id": message_id or row["message_id"],
        "machine_id": row["machine_id"],
        "zone": row["zone"],
        "timestamp": format_ts(ts),
        "temperature": float(row["temperature"]),
        "vibration": float(row["vibration"]),
        "speed": float(row["speed"]),
        "current": float(row["current"]),
        "state": row["state"],
    }
    for name in OPTIONAL_FIELDS:
        if pd.notna(row[name]):
            payload[name] = float(row[name])

    MachineData(**payload)  # raises if the contract is violated
    return payload