import argparse
import os
from threading import Event, Thread
import time

from server.streaming.lj import LabjackT7
from server.streaming.sensors import load_sensors_from_json
from server.testing.virtual_labjack import VirtualLabJack
from server.testing.validators import ValidationReport


def run_test(
    mode: str,
    duration: float,
    config_path: str,
    warmup_reads: int,
):
    sensors = load_sensors_from_json(
        config_path,
        board="T7",
    )

    if not sensors:
        raise RuntimeError(
            f"No T7 sensors loaded from {config_path}"
        )

    print(f"Loaded {len(sensors)} sensors:")
    for sensor in sensors:
        print(f"  {sensor.ain}: {sensor.sensor_type}")

    virtual_ljm = VirtualLabJack(
        sensors=sensors,
        mode=mode,
        scan_rate_hz=10,
    )

    report = ValidationReport()
    outputs = []

    def collect(output):
        outputs.append(output)
        report.add(output)

    t7 = LabjackT7(
        manager=None,
        loop=None,
        ljm_api=virtual_ljm,
        on_sensor_data=collect,
        warmup_reads=warmup_reads,
    )

    t7.open("ANY", "VIRTUAL")

    stop_event = Event()

    worker = Thread(
        target=t7.stream,
        args=(sensors, stop_event),
        daemon=True,
    )

    print(f"\nStarting virtual DAQ in '{mode}' mode...")
    worker.start()

    try:
        time.sleep(duration)

    except KeyboardInterrupt:
        print("Test interrupted.")

    finally:
        stop_event.set()
        t7.stop()
        worker.join(timeout=5)
        t7.close()

    report.print_report()

    print(f"Outputs received: {len(outputs)}")
    print(f"Virtual LJM reads: {virtual_ljm.read_count}")
    print(f"LJM configuration writes: {virtual_ljm.write_history}")

    return report


def main():
    parser = argparse.ArgumentParser(
        description="Virtual LabJack DAQ test harness."
    )

    parser.add_argument(
        "--mode",
        choices=[
            "normal",
            "constant",
            "ramp",
            "noise",
            "missing",
            "invalid",
        ],
        default="normal",
    )

    parser.add_argument(
        "--duration",
        type=float,
        default=10.0,
    )

    parser.add_argument(
        "--config",
        default="labjack_channels.json",
    )

    parser.add_argument(
        "--warmup-reads",
        type=int,
        default=50,
    )

    args = parser.parse_args()

    run_test(
        mode=args.mode,
        duration=args.duration,
        config_path=args.config,
        warmup_reads=args.warmup_reads,
    )


if __name__ == "__main__":
    main()


