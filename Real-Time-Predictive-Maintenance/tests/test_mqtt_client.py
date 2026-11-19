
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
            {
                "fog_id": "fog-a",
                "message": "Hello from Python",
            },
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


def test_mqtt_wildcard_subscription():
    received_messages = []

    subscriber = MQTTClient(
        client_id="test-subscriber-wildcard",
    )

    publisher = MQTTClient(
        client_id="test-publisher-wildcard",
    )

    subscriber.subscribe(
        "fog/+/status",
        lambda payload: received_messages.append(payload),
    )

    subscriber.connect()
    publisher.connect()

    try:
        time.sleep(1)

        publisher.publish(
            "fog/fog-a/status",
            {
                "fog_id": "fog-a",
                "status": "ONLINE",
                "test_id": "wildcard-test",
            },
        )

        publisher.publish(
            "fog/fog-b/status",
            {
                "fog_id": "fog-b",
                "status": "DEGRADED",
                "test_id": "wildcard-test",
            },
        )

        # Wait for the test messages
        for _ in range(20):
            test_messages = [
                message
                for message in received_messages
                if message.get("test_id") == "wildcard-test"
            ]

            if len(test_messages) == 2:
                break

            time.sleep(0.2)

        assert len(test_messages) == 2

        fog_ids = {message["fog_id"] for message in test_messages}

        assert fog_ids == {"fog-a", "fog-b"}

    finally:
        publisher.disconnect()
        subscriber.disconnect()
