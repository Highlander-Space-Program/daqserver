import os
from threading import Lock
from typing import Any, Literal

import paho.mqtt.client as mqtt

from server.logger import server_logger as logger

BreakwireStatus = Literal["unknown", "connected", "broken"]


class ControlPublisher:
    BREAKWIRE_TOPIC = "device/breakwire"
    COMMAND_TOPIC = "device/command"
    BREAKWIRE_PAYLOAD_STATUSES: dict[bytes, BreakwireStatus] = {
        bytes([0x10]): "connected",
        bytes([0x11]): "broken",
    }

    def __init__(self) -> None:
        self._breakwire_status: BreakwireStatus = "unknown"
        self._breakwire_lock = Lock()
        self.client: mqtt.Client | None = None

        mqtt_host = os.getenv("MQTT_HOST")
        mqtt_port_raw = os.getenv("MQTT_PORT", "1883")

        if not mqtt_host:
            logger.warning(
                "MQTT_HOST is not set; control MQTT features are disabled"
            )
            return

        try:
            mqtt_port = int(mqtt_port_raw)
        except ValueError:
            logger.warning(
                "MQTT_PORT must be an integer; control MQTT features are disabled"
            )
            return

        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client = client

        client.on_connect = self._on_connect
        client.on_message = self._on_message

        try:
            client.connect(mqtt_host, mqtt_port)
        except OSError as exc:
            logger.warning(
                "Unable to connect to MQTT broker at %s:%s; control MQTT "
                "features are disabled: %s",
                mqtt_host,
                mqtt_port,
                exc,
            )
            return

        client.loop_start()

    @property
    def is_connected(self) -> bool:
        return self.client is not None

    def send_command(self, control_cmd: int) -> bool:
        if self.client is None:
            return False

        self.client.publish(
            self.COMMAND_TOPIC,
            payload=bytes([control_cmd]),
            qos=2,
        )
        return True

    def get_breakwire_status(self) -> dict[str, BreakwireStatus]:
        with self._breakwire_lock:
            return {"status": self._breakwire_status}

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: Any,
        reason_code: Any,
        properties: Any,
    ) -> None:
        client.subscribe(self.BREAKWIRE_TOPIC, qos=2)

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        msg: mqtt.MQTTMessage,
    ) -> None:
        if msg.topic != self.BREAKWIRE_TOPIC:
            return

        status = self.BREAKWIRE_PAYLOAD_STATUSES.get(msg.payload)
        if status is None:
            return

        with self._breakwire_lock:
            self._breakwire_status = status

    def shutdown(self) -> None:
        if self.client is None:
            return

        self.client.loop_stop()
        self.client.disconnect()
