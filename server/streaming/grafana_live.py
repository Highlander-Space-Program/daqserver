import httpx

from server.pool import Datapool, Topic
from server.models import SensorOutput


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

        self.endpoint = (
            f"{self.url}/api/live/push/{self.stream_id}"
        )

        self.client = httpx.AsyncClient(
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "text/plain",
            }
        )

        self.datapool.subscribe(
            Topic.SENSORDATA,
            self._on_sensor_data,
        )

    async def _on_sensor_data(self, data):
        try:
            sensor_output = data

            # SensorOutput contains the sensor value and metadata.
            entry = sensor_output.data

            source = sensor_output.source.to_dict()

            tags = []

            for key, value in source.items():
                tags.append(f"{key}={value}")

            tags.append(
                f"data_type={sensor_output.data_type.value}"
            )

            tag_string = ",".join(tags)

            payload = (
                f"sensor_data,{tag_string} "
                f"value={entry.value}"
            )

            print("[GrafanaLive] Sending:", payload)

            await self.publish(payload)

        except Exception as exc:
            print("[GrafanaLive] Error:", exc)

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

        await self.client.aclose()

        print("[GrafanaLive] shutdown complete")
