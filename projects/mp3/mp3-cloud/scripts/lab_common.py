"""Conventions et observations synthetiques du laboratoire, sans configuration de production."""

import math
import re
import statistics

PROJECT_PATTERN = r"mp3lab_[0-9a-f]{12}"
RUN_PATTERN = r"lab[0-9a-f]{32}"


def require_run_id(run_id):
    if re.fullmatch(RUN_PATTERN, run_id) is None:
        raise ValueError("Invalid laboratory run identifier")
    return run_id


def validate_state(state):
    if not isinstance(state, dict) or re.fullmatch(
        PROJECT_PATTERN, str(state.get("project", ""))
    ) is None:
        raise ValueError("Refusing an identity outside the mp3lab namespace")
    if state.get("database") != "fog_lab":
        raise ValueError("Refusing a laboratory state pointing to another database")
    api, mqtt = state.get("api_port"), state.get("mqtt_port")
    if type(api) is not int or type(mqtt) is not int or not (
        1024 <= api <= 65531 and 1024 <= mqtt <= 65535 and mqtt not in range(api, api + 5)
    ):
        raise ValueError("Invalid laboratory ports")
    return state


def sensor(identity, machine, zone, timestamp, *, tick=0):
    return {
        "message_id": identity, "machine_id": machine, "zone": zone,
        "timestamp": timestamp.isoformat(), "temperature": 65 + tick % 10 / 10,
        "vibration": 4.8, "speed": 1480, "current": 12.4, "pressure": 6.1,
        "power": 8.3, "frequency": 49.9, "state": "RUNNING",
    }


def prediction(identity, machine, fog, timestamp):
    return {
        "message_id": identity, "machine_id": machine, "fog_id": fog,
        "timestamp": timestamp.isoformat(), "risk_score": .78, "anomaly": True,
        "predicted_fault": "BEARING_WEAR", "severity": "WARNING",
        "model_version": "lab-synthetic-v1",
    }


def distribution(seconds):
    ordered = sorted(seconds)
    if not ordered:
        return {"samples": 0, "p95_ms": None}
    return {
        "samples": len(ordered), "mean_ms": 1000 * statistics.fmean(ordered),
        "p50_ms": 1000 * statistics.median(ordered), "max_ms": 1000 * ordered[-1],
        "p95_ms": 1000 * ordered[math.ceil(.95 * len(ordered)) - 1]
        if len(ordered) >= 100 else None,
        "p99_ms": 1000 * ordered[math.ceil(.99 * len(ordered)) - 1]
        if len(ordered) >= 1000 else None,
    }


def histogram_quantile(buckets, count, quantile=.95):
    """Intervalle du quantile, sans inventer une interpolation des buckets Prometheus."""
    if count < 100:
        return {"samples": int(count), "lower_ms": None, "upper_ms": None}
    lower = 0.
    for bound, cumulative in sorted(buckets.items()):
        if cumulative >= math.ceil(quantile * count):
            return {
                "samples": int(count), "lower_ms": lower * 1000,
                "upper_ms": bound * 1000 if math.isfinite(bound) else None,
                "overflow": not math.isfinite(bound),
            }
        lower = bound
    raise ValueError("Histogram buckets do not cover the observed count")
