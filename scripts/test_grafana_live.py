import asyncio
import os

from dotenv import load_dotenv

from server.streaming.grafana_live import GrafanaLivePublisher


async def main():

    load_dotenv()

    publisher = GrafanaLivePublisher(
        url=os.environ["GRAFANA_URL"],
        token=os.environ["GRAFANA_TOKEN"],
        stream_id=os.getenv("GRAFANA_STREAM_ID", "daq"),
    )

    try:

        for i in range(20):

            value = 20 + i * 0.5

            payload = (
                f"test_sensor,device=test "
                f"value={value}"
            )

            print("Sending:", payload)

            await publisher.publish(payload)

            await asyncio.sleep(1)

    finally:
        await publisher.shutdown()


if __name__ == "__main__":
    asyncio.run(main())
