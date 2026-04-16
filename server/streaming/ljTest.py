import asyncio
from datetime import datetime
from typing import Any

from labjack import ljm

from server.streaming.sensors import Sensor

import time #temporary

# Conversion helpers
def thermocouple_voltage_to_celsius(
    voltage: float, cj_temp_c: float = 25.0
) -> float:
    """K-type thermocouple linear approximation: V → °C."""
    dT_c = voltage / 0.000041
    return cj_temp_c + dT_c


def loadcell_voltage_to_lbs(voltage: float) -> float:
    return ((-0.4995 * (voltage * 1e5)) + 0.8905) * 2.20462


def pressure_voltage_to_psi(voltage: float) -> float:
    return ((voltage - 0.5) / 4.0) * 1600


# LabJack T7 wrapper
class LabJackT7:
    SCAN_RATE_HZ: int = 50
    SCANS_PER_READ: int = 1

    def __init__(self) -> None:
        self.handle = None

    # Connection

    def open(self, connection_type: str = "ANY") -> None:
        print(f"Opening T7 over {connection_type}...")
        self.handle = ljm.openS("T7", connection_type, "192.168.1.3")
        info = ljm.getHandleInfo(self.handle)
        print(
            f"Opened T7 — device: {info[0]}, connection: {info[1]}, "
            f"serial: {info[2]}, IP: {info[3]}"
        )

    def close(self) -> None:
        if self.handle is not None:
            ljm.close(self.handle)
            self.handle = None
            print("LabJack closed.")

    # Stream setup
    def _build_scan_list(self, sensors: list[Sensor]):
        channel_names = [s.ain for s in sensors]
        addresses, _ = ljm.namesToAddresses(len(channel_names), channel_names)
        print("Scan list:")
        for name, addr in zip(channel_names, addresses):
            print(f"  {name} -> {addr}")
        return addresses, channel_names

    def _start_stream(self, scan_list: list, num_channels: int) -> float:
        actual_rate = ljm.eStreamStart(
            self.handle,
            self.SCANS_PER_READ,
            num_channels,
            scan_list,
            self.SCAN_RATE_HZ,
        )
        print(f"Stream started at {actual_rate:.1f} Hz")
        return actual_rate

    # Streaming -> asyncio.Queue
    def stream(
        self,
        sensors: list[Sensor],
        queue: asyncio.Queuem,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """
        Read from the LabJack in a blocking loop and push converted sensor
        readings into *queue* so the FastAPI WebSocket handler can forward
        them to connected browsers.

        Run this in a background thread via loop.run_in_executor() so it
        does not block the asyncio event loop.
        """
        self.open("Ethernet")
        for s in sensors:
            s.configure_labjack(ljm, self)

        scan_list, channel_names = self._build_scan_list(sensors)
        num_channels = len(channel_names)
        sensor_type_by_ain = {s.ain: s.sensor_type for s in sensors}

        self._start_stream(scan_list, num_channels)

        print("Streaming - press Ctrl+C to stop.")
        try:
            while True:
                data, device_backlog, ljm_backlog = ljm.eStreamRead(self.handle)
                scans = len(data) // num_channels
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                packet: dict[str, Any] = {"timestamp": timestamp, "channels": {}}

                for scan_idx in range(scans):
                    base = scan_idx * num_channels
                    for ch_idx, ain in enumerate(channel_names):
                        raw_voltage = data[base + ch_idx]
                        sensor_type = sensor_type_by_ain.get(ain, "")
                        value = self._convert(raw_voltage, sensor_type)
                        packet["channels"][ain] = {
                            "sensor_type": sensor_type,
                            "voltage": raw_voltage,
                            "value": value,
                        }

                # Thread-safe enqueue: drop packet if consumer is too slow
                try:

                    def _safe_put(q, item):
                        try:
                            q.put_nowait(item)
                        except asyncio.QueueFull:
                            pass

                    # time.sleep(0.5) #Delete afterwards just for readability
                    print(packet)
                    loop.call_soon_threadsafe(_safe_put, queue, packet)
                except asyncio.QueueFull:
                    pass

        except KeyboardInterrupt:
            print("Stream interrupted.")
        finally:
            ljm.eStreamStop(self.handle)
            print("Stream stopped.")

    # Unit conversion dispatch
    @staticmethod
    def _convert(voltage: float, sensor_type: str) -> float:
        sensor_type = (sensor_type or "").lower()
        if sensor_type in ("thermocouple", "tc"):
            return thermocouple_voltage_to_celsius(voltage)
        if sensor_type in ("load_cell", "loadcell", "lc"):
            return loadcell_voltage_to_lbs(voltage)
        if sensor_type in ("pressure", "pt"):
            return pressure_voltage_to_psi(voltage)
        return voltage  # raw voltage fallback
