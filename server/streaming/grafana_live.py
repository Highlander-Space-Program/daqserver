
import asyncio

import websockets
from websockets.exceptions import ConnectionClosed


class GrafanaLivePublisher:
    def __init__(
        self,
        url: str,
        token: str,
        stream_id: str = "daq",
    ):
        # Accept either a base URL or a full push endpoint.
        self.url = url.rstrip("/")
        self.token = token
        self.stream_id = stream_id

        if "/api/live/push/" in self.url:
            self.endpoint = self.url
        else:
            self.endpoint = (
                f"{self.url}/api/live/push/{self.stream_id}"
            )

        self.websocket = None
        self._stop = asyncio.Event()
        self._send_lock = asyncio.Lock()

    async def connect(self):
        headers = {
            "Authorization": f"Bearer {self.token}",
        }

        print(f"[GrafanaLive] Connecting to {self.endpoint}")

        self.websocket = await websockets.connect(
            self.endpoint,
            additional_headers=headers,
            ping_interval=20,
            ping_timeout=20,
        )

        print("[GrafanaLive] WebSocket connected")

    async def publish(self, payload: str):
        if self._stop.is_set():
            raise RuntimeError("Grafana Live publisher is shutting down")

        async with self._send_lock:
            if self.websocket is None:
                await self.connect()

            try:
                await self.websocket.send(payload)
                print(f"[GrafanaLive] Sent: {payload}")
            except ConnectionClosed:
                print("[GrafanaLive] Connection closed; reconnecting")

                self.websocket = None
                await self.connect()
                await self.websocket.send(payload)
                print(f"[GrafanaLive] Sent after reconnect: {payload}")

    async def start(self):
        self._stop.clear()
        await self.connect()

        try:
            await self._stop.wait()
        finally:
            await self._close_connection()

    async def _close_connection(self):
        if self.websocket is not None:
            await self.websocket.close()
            self.websocket = None

    async def shutdown(self):
        print("[GrafanaLive] shutting down...")
        self._stop.set()
        await self._close_connection()
        print("[GrafanaLive] shutdown complete")

