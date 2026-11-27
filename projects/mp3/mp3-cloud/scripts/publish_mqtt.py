"""Publie une fixture de contrat ; la confirmation concerne le broker, pas PostgreSQL."""

import argparse
import json
from pathlib import Path
from uuid import uuid4

import paho.mqtt.client as mqtt

from app.config import get_settings
from app.ingest.worker import decode_message
from app.services.ingest import parse_message


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True)
    parser.add_argument("--file", required=True, type=Path)
    parser.add_argument("--repeat", type=int, default=1)
    parser.add_argument("--retain", action="store_true")
    parser.add_argument("--host")
    parser.add_argument("--port", type=int)
    args = parser.parse_args()
    if not 1 <= args.repeat <= 1000:
        parser.error("--repeat must be between 1 and 1000")
    body = json.loads(args.file.read_text(encoding="utf-8"))
    declared_kind = None
    if isinstance(body, dict) and "kind" in body and "payload" in body:
        declared_kind, body = body["kind"], body["payload"]
    payload = json.dumps(body).encode("utf-8")
    item = decode_message(args.topic, payload, args.retain)
    if declared_kind is not None and declared_kind != item["kind"]:
        parser.error("fixture kind does not match topic")
    parse_message(item["kind"], item["payload"])
    settings = get_settings()
    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"mp3-fixture-{uuid4().hex}",
    )
    client.connect(args.host or settings.mqtt_host, args.port or settings.mqtt_port, keepalive=30)
    client.loop_start()
    try:
        for _index in range(args.repeat):
            info = client.publish(args.topic, payload, qos=1, retain=args.retain)
            info.wait_for_publish(timeout=10)
            if not info.is_published():
                raise TimeoutError("broker did not confirm publication")
        print(
            f"{args.repeat} publication(s) confirmed by broker; verify database or worker metrics"
        )
    finally:
        client.disconnect()
        client.loop_stop()


if __name__ == "__main__":
    main()
