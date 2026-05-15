import os
from threading import Lock
from typing import Any, Literal, cast

import paho.mqtt.client as mqtt

BreakwireStatus = Literal["unknown", "connected", "broken"]


class ControlPublisher:
    BREAKWIRE_TOPIC = "device/breakwire"
    COMMAND_TOPIC = "device/command"
    VALID_BREAKWIRE_STATUSES = {"connected", "broken"}

    def __init__(self) -> None:
        self._breakwire_status: BreakwireStatus = "unknown"
        self._breakwire_lock = Lock()

        mqtt_host = os.getenv("MQTT_HOST")
        mqtt_port = int(os.getenv("MQTT_PORT", 1883))

        if mqtt_host is None:
            raise RuntimeError("MQTT_HOST environment variable is required")

        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.client.on_connect = self._on_connect
        self.client.on_message = self._on_message
        self.client.connect(mqtt_host, mqtt_port)
        self.client.loop_start()

    def send_command(self, control_cmd: int) -> None:
        self.client.publish(
            self.COMMAND_TOPIC,
            payload=bytes([control_cmd]),
            qos=2,
        )

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

        try:
            status = msg.payload.decode("utf-8").strip().lower()
        except UnicodeDecodeError:
            return

        if status not in self.VALID_BREAKWIRE_STATUSES:
            return

        with self._breakwire_lock:
            self._breakwire_status = cast(BreakwireStatus, status)

    def shutdown(self) -> None:
        self.client.loop_stop()
        self.client.disconnect()
