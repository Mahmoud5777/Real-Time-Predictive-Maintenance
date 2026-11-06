
import json
import logging
import paho.mqtt.client as mqtt


logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(
        self,
        client_id: str,
        broker_host: str = "127.0.0.1",
        broker_port: int = 1883,
    ):
        self.client = mqtt.Client(
            callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
            client_id=client_id,
            protocol=mqtt.MQTTv311,
        )

        self.broker_host = broker_host
        self.broker_port = broker_port

        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message

        self.message_handlers = {}

    def connect(self):
        self.client.connect(
            self.broker_host,
            self.broker_port,
            keepalive=60,
        )
        self.client.loop_start()

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()

    def _on_connect(self, client, userdata, flags, reason_code, properties):
        if reason_code.is_failure:
            logger.error("MQTT connection failed: %s", reason_code)
            return

        logger.info("Connected to MQTT broker")
        
        for topic in self.message_handlers:
            client.subscribe(topic)

    def _on_disconnect(
        self, client, userdata, disconnect_flags, reason_code, properties
    ):
        logger.warning("Disconnected from MQTT broker: %s", reason_code)

    def publish(self, topic: str, message: dict):
        payload = json.dumps(message)

        result = self.client.publish(topic, payload)

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error("Failed to publish message to %s", topic)

        return result.rc

    def subscribe(self, topic: str, callback):
        self.message_handlers[topic] = callback

        if self.client.is_connected():
            self.client.subscribe(topic)

    def _on_message(self, client, userdata, message):
        try:
            payload = json.loads(message.payload.decode("utf-8"))

            for topic_filter, callback in self.message_handlers.items():
                if mqtt.topic_matches_sub(topic_filter, message.topic):
                    callback(payload)

        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            logger.error("Invalid MQTT message: %s", exc)