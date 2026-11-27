"""Owned metrics and units; unsupported claims are never written as numeric zero."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Metric:
    unit: str
    time_basis: str
    description: str


MEASUREMENTS = {
    "temperature": "degC",
    "vibration": "mm/s",
    "speed": "rpm",
    "current": "A",
    "pressure": "bar",
    "power": "kW",
    "frequency": "Hz",
}
METRICS = {
    **{
        f"mean_{name}": Metric(unit, "sensor.timestamp", "Mean of known measurements")
        for name, unit in MEASUREMENTS.items()
    },
    "measurement_count": Metric("observations", "sensor.timestamp", "Stored measurements"),
    "mean_ingest_latency_s": Metric(
        "s", "sensor.timestamp", "Mean Cloud receipt delay, excluding negative delays"
    ),
    "clock_skew_count": Metric("observations", "sensor.timestamp", "Negative receipt delays"),
    "prediction_count": Metric("predictions", "prediction.timestamp", "Stored predictions"),
    "anomaly_count": Metric("predictions", "prediction.timestamp", "Reported anomalies"),
    "anomaly_ratio": Metric("ratio", "prediction.timestamp", "Fraction reporting anomaly"),
    "mean_risk_score": Metric("ratio", "prediction.timestamp", "Mean reported risk"),
    "critical_prediction_count": Metric(
        "predictions", "prediction.timestamp", "CRITICAL prediction count"
    ),
    "alert_count": Metric("alerts", "alert.timestamp", "Alerts raised in the hour"),
    "critical_alert_count": Metric("alerts", "alert.timestamp", "CRITICAL alerts raised"),
    "mttr_hours": Metric(
        "h", "alert.resolved_at", "Resolution delay of known resolved CRITICAL alerts"
    ),
    "task_event_count": Metric("reports", "task_event.received_at", "Cloud event receipts"),
    "tasks_migrated_total": Metric("reports", "task_event.received_at", "MIGRATED event receipts"),
    "completed_task_reports": Metric(
        "tasks", "task_event.received_at", "Distinct tasks reported COMPLETED in the hour"
    ),
}
UNAVAILABLE = {
    "false_alarm_rate": "No ground-truth alarm labels",
    "model_precision": "No ground-truth prediction labels (TP/FP)",
    "mean_detection_latency_s": "No causal sensor-to-alert linkage",
    "availability_percent": "No complete persistent failure transitions and coverage",
    "mtbf_hours": "No confirmed actual machine failure events",
    "task_recovery_time_s": "No complete failure and actual recovery attempt timestamps",
    "ingest_duplicate_ratio": "Process counters are not durable hourly facts",
}
PREDICTION_METRICS = {
    "prediction_count",
    "anomaly_count",
    "anomaly_ratio",
    "mean_risk_score",
    "critical_prediction_count",
}
