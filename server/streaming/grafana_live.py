import asyncio
import httpx

from server.pool import Topic
from server.streaming.sensors import SensorData, SensorOutput


class GrafanaLivePublisher:

    def __init__(self, url, token, stream_id="daq"):

        self.url = url.rstrip("/")
        self.token = token
        self.stream_id = stream_id

        self.endpoint = (
            f"{self.url}/api/live/push/{self.stream_id}"
        )

        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "text/plain",
            }
        )

        self.running = False

    async def start(self):
        self.running = True

        self.datapool.subscribe(
            Topic.SENSORDATA,
            self.handle_data,
        )

        print("Grafana Live publisher started")
        print(f"Publishing to: {self.endpoint}")

    async def handle_data(self, data: SensorData):
        try:
            lines = self.normalize(data)

            if not lines:
                return

            payload = "\n".join(lines)

            response = await self.client.post(
                self.endpoint,
                content=payload,
            )

            response.raise_for_status()

        except Exception as e:
            print("[GrafanaLive] error:", e)

    def normalize(self, data: SensorData):
        if hasattr(data, "get_data"):
            return self.from_sensor_output(data.get_data())

        raise ValueError(
            f"Unsupported datapool format: {type(data)}"
        )

    def from_sensor_output(
        self,
        sensor_output: SensorOutput,
    ):
        lines = []

        source = sensor_output.source.to_dict()
        measurement = sensor_output.data_type.value

        for entry in sensor_output.data:

            tags = []

            for key, value in source.items():
                if value is not None:
                    tags.append(
                        f"{key}={value}"
                    )

            tags.append(
                f"data_type={sensor_output.data_type.value}"
            )

            tag_string = ""

            if tags:
                tag_string = "," + ",".join(tags)

            timestamp_ns = int(
                entry.time.timestamp() * 1_000_000_000
            )

            line = (
                f"{measurement}"
                f"{tag_string} "
                f"value={float(entry.value)} "
                f"{timestamp_ns}"
            )

            lines.append(line)

        return lines

    async def publish(self, payload: str):
        response = await self.client.post(
            self.endpoint,
            content=payload,
        )

        print(
            "[GrafanaLive]",
            response.status_code,
            response.text,
        )

        response.raise_for_status()


    async def shutdown(self):
        print("[GrafanaLive] shutting down...")

        self.running = False

        await self.client.aclose()

        print("[GrafanaLive] shutdown complete")
