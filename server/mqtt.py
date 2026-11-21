import asyncio
import itertools
import json
import os
from threading import Lock
from typing import Any, Literal

import paho.mqtt.client as mqtt

from server.logger import server_logger as logger

BreakwireStatus = Literal["unknown", "connected", "broken"]

DEFAULT_COMMAND_TIMEOUT_SECONDS = 3.0


class CommandError(Exception):
    """Base class for a control command that did not succeed."""

    def __init__(self, message: str, command: int, command_id: int | None):
        super().__init__(message)
        self.message = message
        self.command = command
        self.command_id = command_id


class PublisherUnavailable(CommandError):
    """MQTT is not connected, so the command was never sent."""


class CommandTimeout(CommandError):
    """The command was sent but the board did not respond in time."""


class CommandRejected(CommandError):
    """The board responded with a non-Ok status."""


class ControlPublisher:
    BREAKWIRE_TOPIC = "device/breakwire"
    COMMAND_TOPIC = "device/command"
    # TODO: placeholder until the board firmware's response topic is finalized
    RESPONSE_TOPIC = "device/command/response"
    BREAKWIRE_PAYLOAD_STATUSES: dict[bytes, BreakwireStatus] = {
        bytes([0x10]): "connected",
        bytes([0x11]): "broken",
    }

    def __init__(self) -> None:
        self._breakwire_status: BreakwireStatus = "unknown"
        self._breakwire_lock = Lock()
        self._pending: dict[int, asyncio.Future] = {}
        self._pending_lock = Lock()
        self._command_ids = itertools.count(1)
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
        self.client = client

    @property
    def is_connected(self) -> bool:
        return self.client is not None

    async def send_command(
        self,
        control_cmd: int,
        timeout: float = DEFAULT_COMMAND_TIMEOUT_SECONDS,
    ) -> dict[str, Any]:
        """Publish a command and wait for the board's matching response.

        Returns the response dict on an "Ok" status. Raises
        PublisherUnavailable, CommandTimeout, or CommandRejected otherwise.
        """
        if self.client is None:
            raise PublisherUnavailable(
                "MQTT control publisher is not connected", control_cmd, None
            )

        future = asyncio.get_running_loop().create_future()
        with self._pending_lock:
            command_id = next(self._command_ids)
            self._pending[command_id] = future

        try:
            self.client.publish(
                self.COMMAND_TOPIC,
                payload=json.dumps({"command": control_cmd, "id": command_id}),
                qos=2,
            )
            try:
                response = await asyncio.wait_for(future, timeout)
            except asyncio.TimeoutError:
                raise CommandTimeout(
                    f"no response from board after {timeout:g}s",
                    control_cmd,
                    command_id,
                ) from None
        finally:
            with self._pending_lock:
                self._pending.pop(command_id, None)

        status = str(response.get("status", ""))
        if status.lower() != "ok":
            message = response.get("message") or f"status {status!r}"
            raise CommandRejected(message, control_cmd, command_id)

        return response

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
        client.subscribe(self.RESPONSE_TOPIC, qos=2)

    def _on_message(
        self,
        client: mqtt.Client,
        userdata: Any,
        msg: mqtt.MQTTMessage,
    ) -> None:
        if msg.topic == self.RESPONSE_TOPIC:
            self._handle_response(msg.payload)
            return

        if msg.topic != self.BREAKWIRE_TOPIC:
            return

        status = self.BREAKWIRE_PAYLOAD_STATUSES.get(msg.payload)
        if status is None:
            return

        with self._breakwire_lock:
            self._breakwire_status = status

    def _handle_response(self, payload: bytes) -> None:
        # Runs on paho's network thread, not the asyncio event loop.
        try:
            response = json.loads(payload)
            command_id = int(response["id"])
        except (ValueError, TypeError, KeyError):
            logger.error("Malformed command response from board: %r", payload)
            return

        with self._pending_lock:
            future = self._pending.pop(command_id, None)

        if future is None:
            logger.warning(
                "Received late or unknown command response for id %s: %r",
                command_id,
                response,
            )
            return

        future.get_loop().call_soon_threadsafe(
            self._resolve_future, future, response
        )

    @staticmethod
    def _resolve_future(future: asyncio.Future, response: dict) -> None:
        if not future.done():
            future.set_result(response)

    def shutdown(self) -> None:
        if self.client is None:
            return

        self.client.loop_stop()
        self.client.disconnect()
