"""Publish a dataset on MQTT, topic fog/{zone}/sensor/{machine_id}.

Replay (historical timestamps, can be accelerated):
    python -m src.publisher --csv data/generated/test.csv --speed 20
Live (real-time, timestamps = now, 1 Hz):
    python -m src.publisher --csv data/generated/test.csv --live
"""
from __future__ import annotations

import argparse
import json
import time
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
import pandas as pd

from .contract import make_message_id, row_to_payload


def publish(csv_path: str, host: str, port: int, speed: float, live: bool,
            qos: int, limit_s: int | None) -> None:
    data = pd.read_csv(csv_path, parse_dates=["timestamp"])
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="mp1-simulator")
    client.connect(host, port, keepalive=30)
    client.loop_start()

    period = 1.0 / (1.0 if live else speed)
    next_tick = time.monotonic()
    sent = 0
    try:
        for i, (_, tick) in enumerate(data.groupby("timestamp", sort=True)):
            if limit_s is not None and i >= limit_s:
                break
            now = datetime.now(timezone.utc)
            for _, row in tick.iterrows():
                if live:   # fresh timestamp + fresh unique id for every emission
                    ts_ms = int(now.timestamp() * 1000)
                    payload = row_to_payload(
                        row, timestamp=now,
                        message_id=make_message_id(row["machine_id"], ts_ms, "live"))
                else:
                    payload = row_to_payload(row)
                topic = f"fog/{payload['zone']}/sensor/{payload['machine_id']}"
                client.publish(topic, json.dumps(payload), qos=qos)
                sent += 1
            next_tick += period
            time.sleep(max(0.0, next_tick - time.monotonic()))
    finally:
        client.loop_stop()
        client.disconnect()
        print(f"{sent} messages published")


def main() -> None:
    p = argparse.ArgumentParser(description="MQTT publisher for MP1 data")
    p.add_argument("--csv", required=True)
    p.add_argument("--host", default="localhost")
    p.add_argument("--port", type=int, default=1883)
    p.add_argument("--speed", type=float, default=1.0, help="replay acceleration")
    p.add_argument("--live", action="store_true", help="timestamps = now, forces 1 Hz")
    p.add_argument("--qos", type=int, default=0, choices=[0, 1])
    p.add_argument("--limit", type=int, default=None, help="stop after N seconds of data")
    a = p.parse_args()
    publish(a.csv, a.host, a.port, a.speed, a.live, a.qos, a.limit)


if __name__ == "__main__":
    main()