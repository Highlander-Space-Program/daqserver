
import asyncio
import os
from datetime import timezone

import websockets
from websockets.exceptions import ConnectionClosed

from server.streaming.sensors import SensorData, SensorOutput


class GrafanaLivePublisher:
    def __init__(
        self,
        url: str | None = None,
        token: str | None = None,
        stream_id: str | None = None,
    ):
        # Accept either a base Grafana URL or the full push endpoint.
        self.url = (
            url or os.getenv("GRAFANA_URL", "ws://localhost:3000")
        ).rstrip("/")

        self.token = token or os.getenv("GRAFANA_TOKEN")

        self.stream_id = stream_id or os.getenv(
            "GRAFANA_STREAM_ID", "daq"
        )

        if not self.token:
            raise ValueError("GRAFANA_TOKEN is not set")

        if "/api/live/push/" in self.url:
            self.endpoint = self.url
        else:
            self.endpoint = (
                f"{self.url}/api/live/push/{self.stream_id}"
            )

        self.websocket = None
        self._send_lock = asyncio.Lock()

    async def connect(self):
        if self.websocket is not None:
            return

        self.websocket = await websockets.connect(
            self.endpoint,
            additional_headers={
                "Authorization": f"Bearer {self.token}"
            },
            ping_interval=20,
            ping_timeout=20,
        )

        print(f"[GrafanaLive] Connected: {self.endpoint}")

    @staticmethod
    def _escape_measurement(value: str) -> str:
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace(",", "\\,")
            .replace(" ", "\\ ")
        )

    @staticmethod
    def _escape_tag(value: str) -> str:
        return (
            str(value)
            .replace("\\", "\\\\")
            .replace(",", "\\,")
            .replace(" ", "\\ ")
            .replace("=", "\\=")
        )

    @classmethod
    def serialize_output(
        cls,
        output: SensorOutput,
        config_ain: str,
    ) -> str:
        """
        Convert the existing SensorOutput into Grafana Live metrics.

        config_ain determines the Grafana Live channel:
        stream/daq/{config_ain.lower()}
        """

        if not config_ain:
            raise ValueError("config_ain cannot be empty")

        # Extract existing sensor metadata.
        source = output.source.to_dict()

        # Use the configured AIN as the measurement name.
        measurement = cls._escape_measurement(
            config_ain.lower()
        )

        # Convert SensorOutput metadata into tags.
        tags = {
            "ain": config_ain.upper(),
            "sensor_type": output.data_type.value.lower(),
        }

        # Preserve physical input metadata.
        for key, value in source.items():
            if value is None:
                continue

            tags[key.lower()] = str(value)

        tag_string = ",".join(
            f"{cls._escape_tag(key)}={cls._escape_tag(value)}"
            for key, value in sorted(tags.items())
        )

        # Convert each TimeBasedData sample into a metric.
        lines = []

        for sample in output.data:
            timestamp = sample.time

            if timestamp.tzinfo is None:
                timestamp = timestamp.astimezone()

            timestamp_ns = int(
                timestamp.astimezone(timezone.utc).timestamp()
                * 1_000_000_000
            )

            lines.append(
                f"{measurement},{tag_string} "
                f"value={float(sample.value)} {timestamp_ns}"
            )

        return "\n".join(lines)

    async def publish_output(
        self,
        output: SensorOutput,
        config_ain: str,
    ):
        """Publish a SensorOutput to its configured Grafana channel."""

        payload = self.serialize_output(output, config_ain)

        if not payload:
            return

        async with self._send_lock:
            for attempt in range(2):
                try:
                    if self.websocket is None:
                        await self.connect()

                    await self.websocket.send(payload)

                    return

                except (ConnectionClosed, OSError) as exc:
                    print(f"[GrafanaLive] Connection error: {exc}")

                    if self.websocket is not None:
                        try:
                            await self.websocket.close()
                        except Exception:
                            pass

                    self.websocket = None

                    if attempt == 1:
                        raise

                    await asyncio.sleep(0.5)

    async def publish_sensor_data(
        self,
        sensor_data: SensorData,
        config_ain: str,
    ):
        """Accept the existing LabJackData wrapper."""

        await self.publish_output(
            sensor_data.get_data(),
            config_ain,
        )

    async def close(self):
        async with self._send_lock:
            if self.websocket is not None:
                await self.websocket.close()
                self.websocket = None

        print("[GrafanaLive] Closed")

