
import time

from mqtt.mqtt_client import MQTTClient


def test_mqtt_publish_and_receive():
    received_messages = []

    subscriber = MQTTClient(
        client_id="test-subscriber",
    )

    publisher = MQTTClient(
        client_id="test-publisher",
    )

    subscriber.subscribe(
        "fog/test/python",
        lambda message: received_messages.append(message),
    )

    subscriber.connect()
    publisher.connect()

    try:
        time.sleep(1)

        publisher.publish(
            "fog/test/python",
            {"fog_id": "fog-a", "message": "Hello from Python"},
        )

        for _ in range(20):
            if received_messages:
                break
            time.sleep(0.2)

        assert len(received_messages) == 1
        assert received_messages[0]["fog_id"] == "fog-a"
        assert received_messages[0]["message"] == "Hello from Python"

    finally:
        publisher.disconnect()
        subscriber.disconnect()
