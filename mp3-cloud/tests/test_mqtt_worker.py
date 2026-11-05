"""Contrat MQTT et decisions d'acquittement sans reseau ni base de travail."""

import asyncio
import json
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import paho.mqtt.client as mqtt
import pytest

from app.config import Settings
from app.ingest import worker as module
from app.ingest.worker import Delivery, InvalidMessage, MqttWorker, decode_message
from app.services.ingest import IngestReport


def make_worker(**changes):
    settings = Settings(_env_file=None).model_copy(update={"mqtt_metrics_port": 0, **changes})
    client = MagicMock()
    client.ack.return_value = mqtt.MQTT_ERR_SUCCESS
    client.subscribe.return_value = (mqtt.MQTT_ERR_SUCCESS, 7)
    client.loop.return_value = mqtt.MQTT_ERR_SUCCESS
    client.loop_write.return_value = mqtt.MQTT_ERR_SUCCESS
    client.loop_misc.return_value = mqtt.MQTT_ERR_SUCCESS
    instance = MqttWorker(settings, MagicMock(), client=client)
    instance._generation = 1
    instance.connected.set()
    return instance


def delivery(payload=b"{}", topic="fog/FOG_A/predictions", generation=1, qos=1):
    return Delivery(topic, payload, 23, qos, False, generation, time.monotonic())


@pytest.mark.parametrize(
    ("topic", "body", "kind"),
    [
        ("fog/A/sensor/M01", {"machine_id": "M01", "zone": "A"}, "sensor"),
        ("fog/FOG_B/predictions", {"machine_id": "M01", "fog_id": "FOG_B"}, "prediction"),
        ("fog/FOG_C/alerts", {"fog_id": "FOG_C"}, "alert"),
        ("fog/FOG_A/status", {"fog_id": "FOG_A"}, "fog_status"),
        ("tasks/events", {"source_fog": "FOG_A", "destination_fog": "FOG_B"}, "task_event"),
    ],
)
def test_topics_preserve_machine_zone_and_allow_cross_zone_processing(topic, body, kind):
    assert decode_message(topic, json.dumps(body).encode()) == {"kind": kind, "payload": body}


@pytest.mark.parametrize(
    ("topic", "payload", "retained", "code"),
    [
        ("fog/B/sensor/M01", b'{"zone":"A"}', False, "TOPIC_MISMATCH"),
        ("fog/A/sensor/M01", b'{"machine_id":"M02"}', False, "TOPIC_MISMATCH"),
        ("fog/FOG_B/predictions", b'{"fog_id":"FOG_A"}', False, "TOPIC_MISMATCH"),
        ("fog/FOG_D/status", b"{}", False, "UNKNOWN_TOPIC"),
        ("fog/A/sensor/M99", b"{}", False, "UNKNOWN_TOPIC"),
        ("tasks/events/extra", b"{}", False, "UNKNOWN_TOPIC"),
        ("tasks/events", b"not-json", False, "INVALID_JSON"),
        ("tasks/events", b"\xff", False, "INVALID_JSON"),
        ("tasks/events", b"[]", False, "INVALID_PAYLOAD"),
        ("fog/FOG_A/alerts", b"{}", True, "RETAIN_NOT_ALLOWED"),
    ],
)
def test_bad_topics_payloads_and_retention_are_rejected(topic, payload, retained, code):
    with pytest.raises(InvalidMessage) as error:
        decode_message(topic, payload, retained)
    assert error.value.code == code


def test_retained_heartbeat_is_allowed():
    assert decode_message("fog/FOG_A/status", b'{"fog_id":"FOG_A"}', True)["kind"] == "fog_status"


@pytest.mark.parametrize("report", [IngestReport(accepted=1), IngestReport(duplicates=1)])
async def test_ack_follows_confirmed_writer_result(monkeypatch, report):
    instance = make_worker()
    session = MagicMock()
    instance.sessions.return_value.__aenter__ = AsyncMock(return_value=session)
    instance.sessions.return_value.__aexit__ = AsyncMock(return_value=False)
    writer = AsyncMock(return_value=report)
    monkeypatch.setattr(module, "persist_batch", writer)
    await instance.process(delivery(), asyncio.Event())
    writer.assert_awaited_once_with(session, [{"kind": "prediction", "payload": {}}])
    instance.client.ack.assert_called_once_with(23, 1)


async def test_invalid_json_is_rejected_and_acknowledged_without_database():
    instance = make_worker()
    await instance.process(delivery(b"not-json"), asyncio.Event())
    instance.sessions.assert_not_called()
    instance.client.ack.assert_called_once_with(23, 1)
    assert (
        instance.metrics.registry.get_sample_value(
            "fog_cloud_mqtt_rejected_total", {"kind": "prediction", "code": "INVALID_JSON"}
        )
        == 1
    )


async def test_temporary_database_error_never_acknowledges(monkeypatch):
    instance = make_worker(mqtt_retry_seconds=0.01)
    instance.sessions.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
    instance.sessions.return_value.__aexit__ = AsyncMock(return_value=False)
    stop = asyncio.Event()

    async def failed(*_args):
        stop.set()
        raise ConnectionResetError("test database failure")

    monkeypatch.setattr(module, "persist_batch", failed)
    await instance.process(delivery(), stop)
    instance.client.ack.assert_not_called()


def test_old_connection_cannot_ack_a_reused_packet_id():
    instance = make_worker()
    instance._generation = 2
    instance._ack(delivery(generation=1))
    instance.client.ack.assert_not_called()
    instance._ack(delivery(generation=2))
    instance.client.ack.assert_called_once_with(23, 1)


def test_qos_zero_has_no_ack():
    instance = make_worker()
    instance._ack(delivery(qos=0))
    instance.client.ack.assert_not_called()


def test_full_queue_pauses_reading_while_allowing_outgoing_packets():
    instance = make_worker(mqtt_queue_capacity=1)
    instance._queue.put_nowait(delivery())
    assert instance._network_step() == mqtt.MQTT_ERR_SUCCESS
    instance.client.loop.assert_not_called()
    instance.client.loop_write.assert_called_once()
    instance.client.loop_misc.assert_called_once()


def test_oversized_payload_does_not_occupy_the_full_buffer():
    instance = make_worker(mqtt_max_payload_bytes=1024)
    incoming = SimpleNamespace(
        topic="tasks/events", payload=b"x" * 2048, mid=1, qos=1, retain=False
    )
    instance._on_message(None, None, incoming)
    queued = instance._queue.get_nowait()
    assert queued.payload == b"" and queued.error == "PAYLOAD_TOO_LARGE"


def test_subscription_readiness_requires_all_topics_in_qos_one():
    instance = make_worker()
    instance.database_ready.set()
    instance._on_connect(instance.client, None, None, SimpleNamespace(is_failure=False), None)
    assert not instance.ready.is_set()
    instance._on_subscribe(None, None, 7, [SimpleNamespace(value=1)] * 5, None)
    assert instance.ready.is_set()
    instance._on_disconnect(None, None, None, None, None)
    assert not instance.ready.is_set()
