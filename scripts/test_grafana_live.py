
import asyncio
import os
import time

import websockets
from dotenv import load_dotenv

load_dotenv()

async def main():
    # Grafana connection settings
    grafana_url = os.getenv("GRAFANA_URL", "ws://localhost:3000").rstrip("/")
    token = os.getenv("GRAFANA_TOKEN")
    stream_id = os.getenv("GRAFANA_STREAM_ID", "daq")

    # Load-test settings
    num_devices = int(os.getenv("NUM_DEVICES", "10"))
    messages_per_second = int(os.getenv("MESSAGES_PER_SECOND", "200"))
    duration_seconds = int(os.getenv("DURATION_SECONDS", "60"))

    if not token:
        raise RuntimeError("Set GRAFANA_TOKEN before running this script")
    if num_devices < 1 or messages_per_second < 1 or duration_seconds < 1:
        raise ValueError("Device count, message rate, and duration must be positive")

    endpoint = f"{grafana_url}/api/live/push/{stream_id}"
    headers = {"Authorization": f"Bearer {token}"}

    interval = 1.0 / messages_per_second
    total_sent = 0
    start_time = time.monotonic()
    next_send = start_time
    next_report = start_time + 1.0

    print(f"Connecting to {endpoint}")
    print(f"Devices: {num_devices}")
    print(f"Target rate: {messages_per_second} messages/second")
    print(f"Duration: {duration_seconds} seconds")

    async with websockets.connect(
        endpoint,
        additional_headers=headers,
        ping_interval=20,
        ping_timeout=20,
    ) as ws:
        print("Connected! Sending simulated sensor data...")

        try:
            while time.monotonic() - start_time < duration_seconds:
                # Rotate among devices so each gets a turn.
                device_index = total_sent % num_devices
                device_id = f"device_{device_index + 1:02d}"

                # Simulate a changing sensor value for each device.
                value = (
                    20.0
                    + device_index
                    + 2.0 * ((total_sent // num_devices) % 10) / 10
                )

                timestamp_ns = time.time_ns()

                # Measurement: test_sensor
                # Tags: device and sensor
                payload = (
                    f"test_sensor,device={device_id},sensor=temperature "
                    f"value={value:.2f} {timestamp_ns}"
                )

                # Grafana Live accepts Influx line protocol.
                await ws.send(payload.encode("utf-8"))
                total_sent += 1

                now = time.monotonic()

                # Print progress once per second.
                if now >= next_report:
                    elapsed = now - start_time
                    actual_rate = total_sent / elapsed if elapsed else 0
                    print(
                        f"Sent: {total_sent} messages | "
                        f"Elapsed: {elapsed:.1f}s | "
                        f"Average rate: {actual_rate:.1f} msg/s"
                    )
                    next_report = now + 1.0

                # Pace messages to target the configured rate.
                next_send += interval
                delay = next_send - time.monotonic()

                if delay > 0:
                    await asyncio.sleep(delay)
                elif delay < -interval * 10:
                    # Recover if the sender falls far behind schedule.
                    next_send = time.monotonic()

        except asyncio.CancelledError:
            raise
        finally:
            elapsed = time.monotonic() - start_time
            print("\nTest finished.")
            print(f"Total messages sent: {total_sent}")
            print(f"Elapsed time: {elapsed:.2f} seconds")
            print(
                f"Average rate: "
                f"{total_sent / elapsed if elapsed else 0:.1f} messages/second"
            )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nTest interrupted.")

