import asyncio
import math
import os
from datetime import datetime, timezone

from dotenv import load_dotenv

from server.streaming.grafana_live import GrafanaLivePublisher
from server.streaming.sensors import (
    DataType,
    SensorOutput,
    T7ID,
    TimeBasedData,
)


async def main():
    load_dotenv()

    publisher = GrafanaLivePublisher()

    # Simulate one thermocouple connected to a LabJack T7.
    source = T7ID(
        mux_number=1,
        cb37_pin="AIN0",
    )

    print("Testing Grafana Live publisher")
    print(f"Endpoint: {publisher.endpoint}")
    print("Press Ctrl+C to stop.\n")

    try:
        await publisher.connect()

        for i in range(1000):
            # Simulated temperature that changes over time.
            value = 30.0 + 5.0 * math.sin(i * 0.1)

            sample = TimeBasedData(
                time=datetime.now(timezone.utc),
                value=value,
            )

            output = SensorOutput(
                data_type=DataType.TC,
                source=source,
                data=[sample],
            )

            # Show the exact payload sent to Grafana.
            payload = publisher.serialize_output(output)
            print(f"Payload: {payload}")

            await publisher.publish_output(output)

            await asyncio.sleep(0.2)

    finally:
        await publisher.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest stopped.")

