
import asyncio
import json

import websockets
from websockets.exceptions import ConnectionClosed

from server.pool import Datapool, Topic

from datetime import datetime, timezone

class GrafanaLivePublisher:
    def __init__(
        self,
        datapool: Datapool,
        url: str,
        token: str,
        stream_id: str = "daq",
    ):
        self.datapool = datapool
        self.url = url.rstrip("/")
        self.token = token
        self.stream_id = stream_id

        # Accept either the Grafana base URL or full push endpoint.
        if "/api/live/push/" in self.url:
            self.endpoint = self.url
        else:
            self.endpoint = (
                f"{self.url}/api/live/push/{self.stream_id}"
            )

        self.websocket = None
        self._stop = asyncio.Event()
        self._send_lock = asyncio.Lock()

        # Subscribe to the same topic used by the LabJack.
        self.datapool.subscribe(
            Topic.SENSORDATA,
            self.on_sensor_data,
        )

    async def connect(self):
        if self.websocket is not None:
            return

        headers = {
            "Authorization": f"Bearer {self.token}",
        }

        self.websocket = await websockets.connect(
            self.endpoint,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=20,
        )

        print(f"[GrafanaLive] Connected: {self.endpoint}")

    async def start(self):
        # Establish the initial connection. publish() can reconnect later.
        await self.connect()

    async def on_sensor_data(self, sensor_data):
        """Datapool callback for each incoming sensor measurement."""
        output = sensor_data.get_data()
        payload = self.to_line_protocol(output)

        if payload:
            await self.publish(payload)

    def to_line_protocol(self, output) -> str:
    """Convert a SensorOutput into one line per sample."""

        measurement = output.data_type.value

        # InputId is a dataclass-like object with to_dict().
        source = output.source.to_dict()

        def escape_tag(value):
            return (
                str(value)
                .replace("\\", "\\\\")
                .replace(",", "\\,")
                .replace(" ", "\\ ")
                .replace("=", "\\=")
            )

        tags = []
        for key in ("mux_number", "cb37_pin", "type", "sensor_type"):
            if key in source:
                tags.append(f"{key}={escape_tag(source[key])}")

        tag_string = "," + ",".join(tags) if tags else ""

        lines = []

        for sample in output.data:
            timestamp = sample.time

            # Convert datetime to Unix nanoseconds.
            if timestamp.tzinfo is None:
                # Assumes naive timestamps represent local system time.
                timestamp = timestamp.astimezone()

            timestamp_ns = int(
                timestamp.astimezone(timezone.utc).timestamp() * 1_000_000_000
            )

            lines.append(
                f"{escape_tag(measurement)}{tag_string} "
                f"value={float(sample.value)} {timestamp_ns}"
            )

        return "\n".join(lines)

    async def publish(self, payload: str):
        async with self._send_lock:
            for attempt in range(2):
                try:
                    if self.websocket is None:
                        await self.connect()

                    await self.websocket.send(payload)
                    print(f"[GrafanaLive] Sent: {payload}")
                    return

                except (ConnectionClosed, OSError) as exc:
                    print(f"[GrafanaLive] Connection error: {exc}")

                    if self.websocket is not None:
                        try:
                            await self.websocket.close()
                        except Exception:
                            pass

                    self.websocket = None

                    if attempt == 0 and not self._stop.is_set():
                        await asyncio.sleep(0.5)
                        continue

                    raise

    async def shutdown(self):
        print("[GrafanaLive] shutting down...")
        self._stop.set()

        # Unsubscribe so future sensor updates aren't sent to a closed client.
        self.datapool.subscribers[Topic.SENSORDATA.value].discard(
            self.on_sensor_data
        )

        if self.websocket is not None:
            await self.websocket.close()
            self.websocket = None

        print("[GrafanaLive] shutdown complete")

