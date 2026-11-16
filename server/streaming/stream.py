import asyncio
import os
from threading import Thread
from concurrent.futures import CancelledError

from server.streaming.lj import LabjackT7
from server.streaming.sensors import load_sensors_from_json
from server.logger import streaming_logger
from server.streaming.switches import CommandExecutor

command_executor = None

def init_streaming(
    loop,
    grafana_publisher=None,
    influx_publisher=None,
    config_path="labjack_channels.json",
):
    global command_executor

    backend_name = os.getenv("DAQ_BACKEND", "real").lower()

    sensors = load_sensors_from_json(
        config_path,
        board="T7",
    )

    if not sensors:
        raise RuntimeError(
            f"No T7 sensors loaded from {config_path}"
        )

    streaming_logger.info(
        "Loaded %d T7 sensors.",
        len(sensors),
    )

    # Start Influx's queue worker, if configured.
    if influx_publisher is not None:
        influx_publisher.start()

    def publish_sensor_output(output):
        # Influx writes independently of Grafana Live.
        if influx_publisher is not None:
            try:
                influx_publisher.publish_output(output)
            except Exception:
                streaming_logger.exception(
                    "Could not queue output for InfluxDB."
                )

        # Grafana Live uses the application's asyncio event loop.
        if grafana_publisher is not None:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    grafana_publisher.publish_output(output),
                    loop,
                )
                future.add_done_callback(
                    lambda f: _log_future_error(
                        f,
                        "Grafana Live publishing failed.",
                    )
                )
            except Exception:
                streaming_logger.exception(
                    "Could not schedule Grafana Live publishing."
                )

    if backend_name == "virtual":
        from server.testing.virtual_labjack import VirtualLabJack

        virtual_ljm = VirtualLabJack(
            sensors=sensors,
            mode=os.getenv("DAQ_VIRTUAL_MODE", "normal"),
            scan_rate_hz=10,
        )

        t7 = LabjackT7(
            manager=None,
            loop=None,
            ljm_api=virtual_ljm,
            on_sensor_data=publish_sensor_output,
        )

        t7.open("ANY", "VIRTUAL")

        command_executor = CommandExecutor(
            handle=t7.handle,
            ljm_api=t7.ljm,
        )

    elif backend_name == "real":
        t7 = LabjackT7(
            manager=None,
            loop=None,
            on_sensor_data=publish_sensor_output,
        )

        t7.open(
            os.getenv("LABJACK_CONNECTION", "Ethernet"),
            os.getenv("LABJACK_IDENTIFIER", "10.10.10.20"),
        )

        command_executor = CommandExecutor(
            handle=t7.handle,
            ljm_api=t7.ljm,
        )

    else:
        raise ValueError(
            f"Unknown DAQ_BACKEND: {backend_name}"
        )

    worker = Thread(
        target=t7.stream,
        args=(sensors,),
        daemon=True,
        name=f"{backend_name}-labjack-stream",
    )
    worker.start()

    streaming_logger.info(
        "Started %s LabJack acquisition.",
        backend_name,
    )

    return t7, worker


def _log_future_error(future, message):
    try:
        future.result()
    except CancelledError:
        pass
    except Exception:
        streaming_logger.exception(message)

def clear_command_executor():
    global command_executor
    command_executor = None


