import argparse
import json
import signal
import time
from datetime import datetime, timezone
from uuid import uuid4

import paho.mqtt.client as mqtt


MACHINES = {
    **{f"M{i:02d}": "A" for i in range(1, 5)},
    **{f"M{i:02d}": "B" for i in range(5, 9)},
    **{f"M{i:02d}": "C" for i in range(9, 13)},
}


def sensor_payload(machine_id: str, zone: str) -> dict:
    tick = time.time_ns()
    temperature = 65.0 + ((tick // 1_000_000) % 25)
    vibration = 3.0 + ((tick // 500_000) % 40) / 10
    return {
        "message_id": str(uuid4()),
        "machine_id": machine_id,
        "zone": zone,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "temperature": temperature,
        "vibration": vibration,
        "speed": 1480.0,
        "current": 12.4,
        "pressure": 6.1,
        "power": 8.3,
        "frequency": 49.9,
        "state": "FAULT" if temperature > 85 or vibration > 6.5 else "RUNNING",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish MP1 industrial sensor readings")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=1883)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--machine", action="append", choices=sorted(MACHINES))
    args = parser.parse_args()

    machine_ids = args.machine or list(MACHINES)
    stop = False

    def handle_signal(_signum, _frame) -> None:
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    client = mqtt.Client(
        callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
        client_id=f"mp1-industrial-simulator-{uuid4()}",
        protocol=mqtt.MQTTv311,
    )
    client.connect(args.host, args.port, keepalive=30)
    client.loop_start()

    try:
        while not stop:
            for machine_id in machine_ids:
                zone = MACHINES[machine_id]
                payload = sensor_payload(machine_id, zone)
                topic = f"fog/{zone}/sensor/{machine_id}"
                client.publish(topic, json.dumps(payload), qos=1, retain=False).wait_for_publish(
                    timeout=5
                )
                print(f"published {topic}", flush=True)
            time.sleep(args.interval)
    finally:
        client.loop_stop()
        client.disconnect()


if __name__ == "__main__":
    main()
