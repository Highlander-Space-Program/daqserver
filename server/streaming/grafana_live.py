import httpx


class GrafanaLivePublisher:

    def __init__(
        self,
        url,
        token,
        stream_id="daq",
    ):
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
