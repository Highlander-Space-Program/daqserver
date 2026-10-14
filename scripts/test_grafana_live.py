
import asyncio
import os
import time

import websockets


async def main():
    base_url = os.getenv(
        "GRAFANA_URL",
        "ws://localhost:3000",
    ).rstrip("/")
    token = os.getenv("GRAFANA_TOKEN")

    if not token:
        raise RuntimeError("Set GRAFANA_TOKEN before running this script")

    stream_id = os.getenv("GRAFANA_STREAM_ID", "daq")
    endpoint = f"{base_url}/api/live/push/{stream_id}"

    headers = {"Authorization": f"Bearer {token}"}

    async with websockets.connect(
        endpoint,
        additional_headers=headers,
        ping_interval=20,
        ping_timeout=20,
    ) as ws:
        print(f"Connected to {endpoint}")

        try:
            for i in range(100):
                timestamp_ns = time.time_ns()
                value = 20.0 + (i % 10)

                payload = (
                    f"test_sensor,device=python_test "
                    f"value={value} {timestamp_ns}"
                )

                # Grafana's WebSocket push examples use binary frames.
                await ws.send(payload.encode("utf-8"))

                print(f"Sent: {payload}")
                await asyncio.sleep(1)

        finally:
            print("Closing WebSocket connection")


if __name__ == "__main__":
    asyncio.run(main())

