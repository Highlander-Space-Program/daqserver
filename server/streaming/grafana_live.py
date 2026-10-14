
import asyncio
import json

import websockets
from websockets.exceptions import ConnectionClosed

from server.pool import Datapool, Topic


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

    async def on_sensor_data(self, data):
        """Datapool callback for each incoming sensor measurement."""
        payload = self.to_line_protocol(data)
        await self.publish(payload)

    def to_line_protocol(self, data) -> str:
        """
        Convert a sensor measurement into Influx line protocol.

        Adapt this method to the exact SensorData schema in sensors.py.
        """
        if hasattr(data, "to_dict"):
            data = data.to_dict()

        if not isinstance(data, dict):
            raise TypeError(
                f"Unsupported sensor data type: {type(data).__name__}"
            )

        measurement = data.get("data_type", "sensor")
        input_id = data.get("input_id", "unknown")
        sample = data.get("data", data)

        if not isinstance(sample, dict):
            raise ValueError("Sensor data must contain a data dictionary")

        value = sample.get("value")
        timestamp = sample.get("time")

        if value is None:
            raise ValueError("Sensor measurement has no value")

        # Escape Influx line-protocol tag/measurement characters.
        measurement = str(measurement).replace("\\", "\\\\")
        measurement = measurement.replace(",", "\\,").replace(" ", "\\ ")
        input_id = str(input_id).replace("\\", "\\\\")
        input_id = input_id.replace(",", "\\,").replace(" ", "\\ ")

        # Influx timestamps must be integer nanoseconds.
        if timestamp is None:
            import time
            timestamp = time.time_ns()
        else:
            timestamp = int(timestamp)

        return (
            f"{measurement},input_id={input_id} "
            f"value={float(value)} {timestamp}"
        )

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

