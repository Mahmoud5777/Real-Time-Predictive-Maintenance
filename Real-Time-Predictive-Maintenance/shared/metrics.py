
import csv
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    CONTENT_TYPE_LATEST,
)


class MetricsCollector:
    def __init__(self):
        self.registry = CollectorRegistry()
        self.lock = threading.Lock()
        self.history = []

        self.tasks_completed = Counter(
            "fog_tasks_completed_total",
            "Number of completed tasks",
            ["fog_id", "task_type"],
            registry=self.registry,
        )

        self.tasks_failed = Counter(
            "fog_tasks_failed_total",
            "Number of failed tasks",
            ["fog_id", "task_type"],
            registry=self.registry,
        )

        self.migrations = Counter(
            "fog_migrations_total",
            "Number of task migrations",
            ["source", "destination", "kind"],
            registry=self.registry,
        )

        self.dispatch_latency = Histogram(
            "scheduler_dispatch_latency_seconds",
            "Time needed to dispatch a task",
            registry=self.registry,
        )

        self.queue_wait = Histogram(
            "fog_queue_wait_seconds",
            "Time a task waits in the queue",
            ["fog_id"],
            registry=self.registry,
        )

        self.processing_time = Histogram(
            "fog_processing_time_seconds",
            "Task processing duration",
            ["fog_id"],
            registry=self.registry,
        )

        self.end_to_end = Histogram(
            "fog_end_to_end_latency_seconds",
            "Task end-to-end latency",
            ["fog_id"],
            registry=self.registry,
        )

        self.recovery_rto = Histogram(
            "fog_recovery_rto_seconds",
            "Time required to reassign tasks after failure detection",
            ["failed_fog"],
            registry=self.registry,
        )

        self.cpu_usage = Gauge(
            "fog_cpu_usage_percent",
            "Fog CPU usage percentage",
            ["fog_id"],
            registry=self.registry,
        )

        self.ram_usage = Gauge(
            "fog_ram_usage_percent",
            "Fog RAM usage percentage",
            ["fog_id"],
            registry=self.registry,
        )

        self.queue_size = Gauge(
            "fog_queue_size",
            "Number of queued tasks",
            ["fog_id"],
            registry=self.registry,
        )

    def _record(self, metric, value, **labels):
        with self.lock:
            self.history.append({
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "metric": metric,
                "value": value,
                "labels": json.dumps(labels),
            })

    def record_task_completion(
        self,
        fog_id,
        task_type,
        status,
        queue_wait_ms=None,
        processing_time_ms=None,
        end_to_end_ms=None,
    ):
        if status == "COMPLETED":
            self.tasks_completed.labels(fog_id, task_type).inc()
        elif status == "FAILED":
            self.tasks_failed.labels(fog_id, task_type).inc()

        timings = {
            "queue_wait_ms": queue_wait_ms,
            "processing_time_ms": processing_time_ms,
            "end_to_end_ms": end_to_end_ms,
        }

        for name, value in timings.items():
            if value is not None:
                self._record(name, value, fog_id=fog_id)

        if queue_wait_ms is not None:
            self.queue_wait.labels(fog_id).observe(
                max(queue_wait_ms, 0) / 1000
            )

        if processing_time_ms is not None:
            self.processing_time.labels(fog_id).observe(
                max(processing_time_ms, 0) / 1000
            )

        if end_to_end_ms is not None:
            self.end_to_end.labels(fog_id).observe(
                max(end_to_end_ms, 0) / 1000
            )

    def record_dispatch(self, duration_ms):
        self.dispatch_latency.observe(max(duration_ms, 0) / 1000)
        self._record("dispatch_latency_ms", duration_ms)

    def record_migration(self, source, destination, kind="SCHEDULING"):
        self.migrations.labels(source, destination, kind).inc()
        self._record(
            "migration",
            1,
            source=source,
            destination=destination,
            kind=kind,
        )

    def record_node_snapshot(self, fog_id, cpu, ram, queued_tasks):
        self.cpu_usage.labels(fog_id).set(cpu)
        self.ram_usage.labels(fog_id).set(ram)
        self.queue_size.labels(fog_id).set(queued_tasks)

        with self.lock:
            timestamp = datetime.now(timezone.utc).isoformat()
            self.history.extend([
                {
                    "timestamp": timestamp,
                    "metric": "cpu_percent",
                    "value": cpu,
                    "labels": json.dumps({"fog_id": fog_id}),
                },
                {
                    "timestamp": timestamp,
                    "metric": "ram_percent",
                    "value": ram,
                    "labels": json.dumps({"fog_id": fog_id}),
                },
                {
                    "timestamp": timestamp,
                    "metric": "queued_tasks",
                    "value": queued_tasks,
                    "labels": json.dumps({"fog_id": fog_id}),
                },
            ])

    def record_recovery_rto(self, failed_fog, duration_seconds):
        self.recovery_rto.labels(failed_fog).observe(
            max(duration_seconds, 0)
        )
        self._record(
            "recovery_rto_seconds",
            duration_seconds,
            failed_fog=failed_fog,
        )

    def export_csv(self, destination="reports/metrics.csv"):
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)

        with self.lock:
            rows = list(self.history)

        with path.open("w", newline="", encoding="utf-8") as file:
            writer = csv.DictWriter(
                file,
                fieldnames=["timestamp", "metric", "value", "labels"],
            )
            writer.writeheader()
            writer.writerows(rows)

        return str(path)

    def prometheus_data(self):
        return generate_latest(self.registry)

    @property
    def prometheus_content_type(self):
        return CONTENT_TYPE_LATEST


metrics = MetricsCollector()
