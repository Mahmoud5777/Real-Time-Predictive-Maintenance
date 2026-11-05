"""Etape 4 : consommateur MQTT autonome, commit PostgreSQL puis acquittement QoS 1."""

import asyncio
import json
import logging
import queue
import re
import signal
import threading
import time
from dataclasses import dataclass
from typing import Any

import paho.mqtt.client as mqtt
from prometheus_client import CollectorRegistry, Counter, Gauge, Histogram, start_http_server
from sqlalchemy import func, select, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.exc import TimeoutError as DatabaseTimeout
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.config import Settings, get_settings
from app.models.tables import FogNode, Machine
from app.services.ingest import persist_batch

LOGGER = logging.getLogger(__name__)
TOPIC_KIND = {
    "fog/+/predictions": "prediction",
    "fog/+/alerts": "alert",
    "fog/+/status": "fog_status",
    "tasks/events": "task_event",
    "fog/+/sensor/+": "sensor",
}
DATABASE_FAILURES = (DBAPIError, DatabaseTimeout, OSError, TimeoutError)


class InvalidMessage(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def topic_kind(topic: str) -> tuple[str, dict[str, str]]:
    """La zone sensor reste celle de la machine, quel que soit l'executant."""
    if topic == "tasks/events":
        return "task_event", {}
    parts = topic.split("/")
    if len(parts) == 4 and parts[0] == "fog" and parts[2] == "sensor":
        if parts[1] in {"A", "B", "C"} and re.fullmatch(r"M(0[1-9]|1[0-2])", parts[3]):
            return "sensor", {"zone": parts[1], "machine_id": parts[3]}
    if len(parts) == 3 and parts[0] == "fog" and parts[1] in {"FOG_A", "FOG_B", "FOG_C"}:
        kind = {"predictions": "prediction", "alerts": "alert", "status": "fog_status"}.get(
            parts[2]
        )
        if kind is not None:
            return kind, {"fog_id": parts[1]}
    raise InvalidMessage("UNKNOWN_TOPIC")


def decode_message(topic: str, payload: bytes, retained: bool = False) -> dict[str, Any]:
    kind, expected = topic_kind(topic)
    if retained and kind != "fog_status":
        raise InvalidMessage("RETAIN_NOT_ALLOWED")
    try:
        body = json.loads(payload.decode("utf-8"))
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise InvalidMessage("INVALID_JSON") from exc
    if not isinstance(body, dict):
        raise InvalidMessage("INVALID_PAYLOAD")
    if any(key in body and body[key] != value for key, value in expected.items()):
        raise InvalidMessage("TOPIC_MISMATCH")
    return {"kind": kind, "payload": body}


@dataclass(frozen=True)
class Delivery:
    topic: str
    payload: bytes
    mid: int
    qos: int
    retained: bool
    generation: int
    received_monotonic: float
    error: str | None = None


class WorkerMetrics:
    def __init__(self) -> None:
        self.registry = CollectorRegistry()

        def counter(name, description, labels=()):
            return Counter(f"fog_cloud_mqtt_{name}", description, labels, registry=self.registry)

        def gauge(name, description):
            return Gauge(f"fog_cloud_mqtt_{name}", description, registry=self.registry)

        self.received = counter("received_total", "Messages recus", ["qos"])
        self.accepted = counter("accepted_total", "Nouveaux messages confirmes", ["kind"])
        self.duplicates = counter("duplicates_total", "Retransmissions identiques", ["kind"])
        self.rejected = counter("rejected_total", "Rejets definitifs", ["kind", "code"])
        self.retries = counter("retries_total", "Erreurs temporaires", ["stage"])
        self.connections = counter("connections_total", "Connexions MQTT etablies")
        self.acks = counter("acknowledgements_total", "ACK emis apres decision definitive")
        self.stale = counter("stale_ack_skipped_total", "ACK ignores pour une ancienne connexion")
        self.pressure = counter("backpressure_total", "Episodes de pause de lecture reseau")
        self.connected = gauge("connected", "Connexion MQTT connue")
        self.database_ready = gauge("database_ready", "Derniere verification de base reussie")
        self.ready = gauge("ready", "Base prete et abonnements confirmes")
        self.depth = gauge("queue_depth", "Messages en attente, y compris le tampon supplementaire")
        self.last_received = gauge("last_received_timestamp_seconds", "Derniere reception UTC Unix")
        self.latency = Histogram(
            "fog_cloud_mqtt_processing_seconds",
            "Reception jusqu'a decision definitive",
            registry=self.registry,
        )


class MqttWorker:
    def __init__(self, settings: Settings, sessions, *, client=None) -> None:
        self.settings = settings
        self.sessions = sessions
        self.metrics = WorkerMetrics()
        self.client = client or mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=settings.mqtt_client_id,
            clean_session=False,
            protocol=mqtt.MQTTv311,
            manual_ack=True,
        )
        self.client.connect_timeout = settings.mqtt_connect_timeout_seconds
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_subscribe = self._on_subscribe
        self.client.on_message = self._on_message
        self._lock = threading.RLock()
        self._queue: queue.Queue[Delivery] = queue.Queue(settings.mqtt_queue_capacity)
        self._pending: Delivery | None = None
        self._generation = 0
        self._subscribe_mid = None
        self._need_connect = True
        self._pressure = False
        self._loop = None
        self._available = asyncio.Event()
        self.connected = threading.Event()
        self.subscribed = threading.Event()
        self.database_ready = threading.Event()
        self.ready = threading.Event()

    def _refresh_ready(self) -> None:
        ready = (
            self.connected.is_set() and self.subscribed.is_set() and self.database_ready.is_set()
        )
        self.ready.set() if ready else self.ready.clear()
        self.metrics.ready.set(int(ready))
        self.metrics.connected.set(int(self.connected.is_set()))
        self.metrics.database_ready.set(int(self.database_ready.is_set()))

    def _on_connect(self, client, _userdata, _flags, reason_code, _properties) -> None:
        with self._lock:
            if reason_code.is_failure:
                self._need_connect = True
                return
            self._generation += 1
            self.connected.set()
            self.subscribed.clear()
            self.metrics.connections.inc()
            result, self._subscribe_mid = client.subscribe([(topic, 1) for topic in TOPIC_KIND])
            self._need_connect = result != mqtt.MQTT_ERR_SUCCESS
            self._refresh_ready()
        LOGGER.info("MQTT connected; waiting for subscription confirmation")

    def _on_subscribe(self, _client, _userdata, mid, reason_codes, _properties) -> None:
        with self._lock:
            if mid != self._subscribe_mid:
                return
            if len(reason_codes) != len(TOPIC_KIND) or any(x.value != 1 for x in reason_codes):
                self._need_connect = True
                self.subscribed.clear()
                LOGGER.error("MQTT subscriptions rejected")
            else:
                self.subscribed.set()
            self._refresh_ready()

    def _on_disconnect(self, _client, _userdata, _flags, _reason, _properties) -> None:
        with self._lock:
            self.connected.clear()
            self.subscribed.clear()
            self._need_connect = True
            self._refresh_ready()

    def _update_depth(self) -> None:
        self.metrics.depth.set(self._queue.qsize() + int(self._pending is not None))

    def _on_message(self, _client, _userdata, message) -> None:
        with self._lock:
            oversized = len(message.payload) > self.settings.mqtt_max_payload_bytes
            delivery = Delivery(
                message.topic,
                b"" if oversized else bytes(message.payload),
                message.mid,
                message.qos,
                bool(message.retain),
                self._generation,
                time.monotonic(),
                "PAYLOAD_TOO_LARGE" if oversized else None,
            )
            self.metrics.received.labels(str(message.qos)).inc()
            self.metrics.last_received.set(time.time())
            try:
                self._queue.put_nowait(delivery)
            except queue.Full:
                # Un seul tampon supplementaire, puis la boucle cesse de lire.
                if self._pending is not None:
                    raise RuntimeError("MQTT intake exceeded the bounded delivery buffer") from None
                self._pending = delivery
            self._update_depth()
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._available.set)

    def _network_step(self) -> int:
        with self._lock:
            if self._pending is not None and not self._queue.full():
                self._queue.put_nowait(self._pending)
                self._pending = None
                self._update_depth()
            full = self._queue.full() or self._pending is not None
            if full:
                if not self._pressure:
                    self.metrics.pressure.inc()
                self._pressure = True
                # Conserver les ACK et keepalives sortants pendant la pause de lecture.
                result = self.client.loop_write()
                return result if result else self.client.loop_misc()
            self._pressure = False
            return self.client.loop(timeout=0.1)

    def _connect(self) -> None:
        with self._lock:
            self.connected.clear()
            self.subscribed.clear()
            self._refresh_ready()
            self.client.connect(
                self.settings.mqtt_host,
                self.settings.mqtt_port,
                keepalive=self.settings.mqtt_keepalive_seconds,
            )
            self._need_connect = False

    @staticmethod
    async def _pause(stop: asyncio.Event, seconds: float) -> None:
        try:
            await asyncio.wait_for(stop.wait(), timeout=seconds)
        except TimeoutError:
            pass

    async def _network(self, stop: asyncio.Event) -> None:
        delay = self.settings.mqtt_retry_seconds
        while not stop.is_set():
            try:
                if self._need_connect:
                    await asyncio.to_thread(self._connect)
                result = await asyncio.to_thread(self._network_step)
                if result != mqtt.MQTT_ERR_SUCCESS:
                    raise OSError("MQTT network unavailable")
                if self.connected.is_set():
                    delay = self.settings.mqtt_retry_seconds
                await self._pause(stop, 0.02)
            except OSError as exc:
                with self._lock:
                    self.connected.clear()
                    self.subscribed.clear()
                    self._need_connect = True
                    self._refresh_ready()
                self.metrics.retries.labels("mqtt").inc()
                LOGGER.warning("MQTT retry: %s", type(exc).__name__)
                await self._pause(stop, delay)
                delay = min(delay * 2, self.settings.mqtt_retry_max_seconds)

    async def _wait_database(self, stop: asyncio.Event) -> bool:
        while not stop.is_set():
            try:
                async with asyncio.timeout(self.settings.mqtt_database_timeout_seconds):
                    async with self.sessions() as session:
                        revision = await session.scalar(
                            text("SELECT version_num FROM alembic_version")
                        )
                        fogs = await session.scalar(select(func.count()).select_from(FogNode))
                        machines = await session.scalar(select(func.count()).select_from(Machine))
                        tables = await session.scalar(
                            text("""
                            SELECT count(*) FROM information_schema.tables
                            WHERE table_schema = 'public' AND table_name IN (
                                'machines', 'fog_nodes', 'sensor_data', 'predictions', 'alerts',
                                'fog_status_history', 'tasks', 'task_events', 'kpi_records'
                            )
                        """)
                        )
                        if not revision or tables != 9 or fogs != 3 or machines != 12:
                            raise OSError("schema or catalogue not ready")
                self.database_ready.set()
                self._refresh_ready()
                return True
            except DATABASE_FAILURES as exc:
                self.metrics.retries.labels("startup").inc()
                LOGGER.warning("Waiting for schema/catalogue: %s", type(exc).__name__)
                await self._pause(stop, self.settings.mqtt_retry_seconds)
        return False

    def _ack(self, delivery: Delivery) -> None:
        if delivery.qos == 0:
            return
        with self._lock:
            if not self.connected.is_set() or delivery.generation != self._generation:
                self.metrics.stale.inc()
                return
            if self.client.ack(delivery.mid, delivery.qos) == mqtt.MQTT_ERR_SUCCESS:
                self.metrics.acks.inc()

    def _reject(self, kind: str, code: str) -> None:
        self.metrics.rejected.labels(kind, code).inc()
        LOGGER.warning("MQTT message rejected: kind=%s code=%s", kind, code)

    async def process(self, delivery: Delivery, stop: asyncio.Event) -> None:
        kind = "unknown"
        try:
            kind, _expected = topic_kind(delivery.topic)
            if delivery.error is not None:
                raise InvalidMessage(delivery.error)
            item = decode_message(delivery.topic, delivery.payload, delivery.retained)
        except InvalidMessage as exc:
            self._reject(kind, exc.code)
            await asyncio.to_thread(self._ack, delivery)
            return
        delay = self.settings.mqtt_retry_seconds
        while not stop.is_set():
            try:
                async with asyncio.timeout(self.settings.mqtt_database_timeout_seconds):
                    async with self.sessions() as session:
                        report = await persist_batch(session, [item])
                self.database_ready.set()
                self._refresh_ready()
                self.metrics.accepted.labels(kind).inc(report.accepted)
                self.metrics.duplicates.labels(kind).inc(report.duplicates)
                for error in report.errors:
                    self._reject(kind, error["code"])
                self.metrics.latency.observe(time.monotonic() - delivery.received_monotonic)
                await asyncio.to_thread(self._ack, delivery)
                return
            except DATABASE_FAILURES as exc:
                self.database_ready.clear()
                self._refresh_ready()
                self.metrics.retries.labels("database").inc()
                LOGGER.warning("Storage retry without ACK: %s", type(exc).__name__)
                await self._pause(stop, delay)
                delay = min(delay * 2, self.settings.mqtt_retry_max_seconds)

    async def _consume(self, stop: asyncio.Event) -> None:
        while not stop.is_set():
            self._available.clear()
            try:
                delivery = self._queue.get_nowait()
            except queue.Empty:
                try:
                    await asyncio.wait_for(self._available.wait(), timeout=0.1)
                except TimeoutError:
                    pass
                continue
            self._update_depth()
            try:
                await self.process(delivery, stop)
            finally:
                self._queue.task_done()

    def _disconnect(self) -> None:
        with self._lock:
            self.client.disconnect()
            self.connected.clear()
            self.subscribed.clear()
            self._refresh_ready()

    async def run(self, stop: asyncio.Event) -> None:
        self._loop = asyncio.get_running_loop()
        server = None
        tasks = []
        try:
            if self.settings.mqtt_metrics_port:
                server, _thread = start_http_server(
                    self.settings.mqtt_metrics_port,
                    addr=self.settings.mqtt_metrics_host,
                    registry=self.metrics.registry,
                )
            if not await self._wait_database(stop):
                return
            tasks = [
                asyncio.create_task(self._network(stop)),
                asyncio.create_task(self._consume(stop)),
            ]
            stopped = asyncio.create_task(stop.wait())
            tasks.append(stopped)
            done, _pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in done:
                task.result()
        finally:
            stop.set()
            if tasks:
                _done, pending = await asyncio.wait(
                    tasks, timeout=self.settings.mqtt_shutdown_seconds
                )
                for task in pending:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
            await asyncio.to_thread(self._disconnect)
            if server is not None:
                await asyncio.to_thread(server.shutdown)
                server.server_close()


async def serve() -> None:
    settings = get_settings()
    logging.basicConfig(level=settings.log_level.upper(), format="%(levelname)s %(message)s")
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    previous = signal.getsignal(signal.SIGTERM)
    signal.signal(signal.SIGTERM, lambda *_args: loop.call_soon_threadsafe(stop.set))
    engine = create_async_engine(
        settings.database_url,
        pool_pre_ping=True,
        connect_args={"timeout": settings.mqtt_database_timeout_seconds},
    )
    try:
        await MqttWorker(settings, async_sessionmaker(engine, expire_on_commit=False)).run(stop)
    finally:
        signal.signal(signal.SIGTERM, previous)
        await engine.dispose()


def main() -> None:
    try:
        asyncio.run(serve())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
