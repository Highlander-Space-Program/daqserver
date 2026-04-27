import asyncio
from datetime import datetime
from typing import Any
from collections import deque
from labjack import ljm
from server.streaming.sensors import Sensor
import numpy as np
from threading import Thread
from server.pool import Datapool, Topic


def calibration1(voltage):
    return 115918.38800425902 * voltage + -3.743950002152496


def calibration2(voltage):
    return 120315.08079063638 * voltage + -4.1362754116597245


def calibration3(voltage):
    return 118278.07807607231 * voltage + 6.439642411975598


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


def loadcell_voltage_to_lbs_formula(
    voltage: float,
    rated_capacity_kg: float,
    rated_output_mv_per_v: float,  # use 2.0 for 300kg cell, 40.58 for QL-TSC (202.9/5V)
    excitation_voltage: float,
    zero_offset_v: float = 0.0,
) -> float:
    full_scale_voltage = (rated_output_mv_per_v / 1000.0) * excitation_voltage
    net_voltage = voltage - zero_offset_v
    load_kg = (net_voltage / full_scale_voltage) * rated_capacity_kg
    return load_kg * 2.20462


# LabJack wrapper
class Labjack:
    SCAN_RATE_HZ: int = 100
    SCANS_PER_READ: int = 1

    def __init__(self, datapool: Datapool) -> None:
        self.handle = None
        self.datapool = datapool
        self._buffers: dict[str, deque] = {}
        self._tare: dict[str, float] = {}
        self.device = "UNKNOWN"

    # Connection
    def open(self, connection_type: str = "ANY") -> None:
        raise NotImplementedError()

    def close(self) -> None:
        if self.handle is not None:
            ljm.close(self.handle)
            self.handle = None
            print("LabJack closed.")

    SMOOTHING_WINDOWS = {  # rename to plural + make it a dict
        "thermocouple": 10,
        "tc": 10,
        "load_cell": 50,
        "loadcell": 50,
        "lc": 50,
        "pressure": 20,
        "pt": 20,
    }

    # Rolling Average
    def _smooth(self, ain: str, value: float, sensor_type: str = "") -> float:
        window = self.SMOOTHING_WINDOWS.get(sensor_type.lower(), 25)
        if ain not in self._buffers:
            self._buffers[ain] = deque(
                [value] * window, maxlen=window
            )  # create buffer first
        self._buffers[ain].append(value)
        avg = sum(self._buffers[ain]) / len(self._buffers[ain])
        return avg - self._tare.get(ain, 0.0)

    # Tare
    def tare(self, sensor_type_by_ain: dict[str, str], ain: str = None) -> None:
        """
        Tare a specific channel or all channels if ain is None.
        Call this when no load is applied.
        """
        if ain:
            # Get current average value from buffer as the tare offset
            if ain in self._buffers:
                self._tare[ain] = sum(self._buffers[ain]) / len(
                    self._buffers[ain]
                )
                print(f"Tared {ain}: offset = {self._tare[ain]:.4f}")
        else:
            # Tare all channels at once
            for ch, buf in self._buffers.items():
                sensor_type = sensor_type_by_ain.get(ch, "").lower()
                if sensor_type == "loadcell":
                    self._tare[ch] = sum(buf) / len(buf)
                    print(f"Tared {ch}: offset = {self._tare[ch]:.4f}")

    # Stream setup
    def _build_scan_list(self, sensors: list[Sensor]):
        for s in sensors:
            print(s)
        channel_names = [s.ain for s in sensors]
        addresses, _ = ljm.namesToAddresses(len(channel_names), channel_names)
        print("Scan list:")
        for name, addr in zip(channel_names, addresses):
            print(f"  {name} -> {addr}")
        return addresses, channel_names

    def _start_stream(self, scan_list: list, num_channels: int) -> float:
        ljm.eWriteName(self.handle, "STREAM_RESOLUTION_INDEX", 0)
        ljm.eWriteName(self.handle, "STREAM_SETTLING_US", 100)

        # Testing
        settling = ljm.eReadName(self.handle, "STREAM_SETTLING_US")
        print(f"Settling time: {settling} µs")

        actual_rate = ljm.eStreamStart(
            self.handle,
            self.SCANS_PER_READ,
            num_channels,
            scan_list,
            self.SCAN_RATE_HZ,
        )
        print(f"Stream started at {actual_rate:.1f} Hz")
        return actual_rate

    def not_blocking_streaming():
        raise NotImplementedError

    # Streaming -> datapool
    def stream(
        self,
        sensors: list[Sensor],
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

        # Warm up
        for _ in range(50):
            data, _, _ = ljm.eStreamRead(self.handle)
            for ch_idx, ain in enumerate(channel_names):
                raw_voltage = data[ch_idx]
                sensor_type = sensor_type_by_ain[ain]
                value = self._convert(raw_voltage, sensor_type, ain)
                self._smooth(ain, value, sensor_type)

        print("Streaming - press Ctrl+C to stop.")
        try:
            while True:
                data, device_backlog, ljm_backlog = ljm.eStreamRead(self.handle)
                scans = len(data) // num_channels
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]

                packet: dict[str, Any] = {
                    "device": self.device,
                    "timestamp": timestamp,
                    "channels": {},
                }

                for scan_idx in range(scans):
                    base = scan_idx * num_channels
                    for ch_idx, ain in enumerate(channel_names):
                        raw_voltage = data[base + ch_idx]
                        sensor_type = sensor_type_by_ain.get(ain, "")
                        value = self._convert(raw_voltage, sensor_type, ain)
                        value = self._smooth(ain, value, sensor_type)
                        packet["channels"][ain] = {
                            "sensor_type": sensor_type,
                            "voltage": raw_voltage,
                            "value": value,
                        }

                try:
                    print(packet)
                    self.datapool.publish(Topic.SENSORDATA, packet)

                except asyncio.QueueFull:
                    pass

                    # Continue here

        except KeyboardInterrupt:
            print("Stream interrupted.")
        finally:
            ljm.eStreamStop(self.handle)
            print("Stream stopped.")

    # Unit conversion dispatch
    @staticmethod
    def _convert(voltage: float, sensor_type: str, ain: str) -> float:
        sensor_type = (sensor_type or "").lower()
        if sensor_type in ("thermocouple", "tc"):
            return thermocouple_voltage_to_celsius(voltage)
        if sensor_type in ("load_cell", "loadcell", "lc"):
            if ain == "AIN0":
                return calibration1(voltage)
            if ain == "AIN2":
                return calibration2(voltage)
            if ain == "AIN3":
                return calibration3(voltage)
            # return loadcell_voltage_to_lbs_formula(voltage, 1000, 2, 5)
        if sensor_type in ("pressure", "pt"):
            return pressure_voltage_to_psi(voltage)
        return voltage  # raw voltage fallback


class LabjackT8(Labjack):
    def __init__(self, datapool: Datapool) -> None:
        super().__init__(datapool)
        self.device = "T8"

    def open(self, connection_type: str = "ANY") -> None:
        print(f"Opening T8 over {connection_type}...")
        self.handle = ljm.openS("T8", connection_type, "192.168.1.208")
        info = ljm.getHandleInfo(self.handle)
        print(
            f"Opened T8 — device: {info[0]}, connection: {info[1]}, "
            f"serial: {info[2]}, IP: {info[3]}"
        )


class LabjackT7(Labjack):
    def __init__(self, datapool: Datapool) -> None:
        super().__init__(datapool)
        self.device = "T7"

    def open(self, connection_type: str = "ANY") -> None:
        print(f"Opening T7 over {connection_type}...")
        self.handle = ljm.openS("T7", connection_type, "192.168.1.3")

        print("LabJack state reset.")

        info = ljm.getHandleInfo(self.handle)
        print(
            f"Opened T7 — device: {info[0]}, connection: {info[1]}, "
            f"serial: {info[2]}, IP: {info[3]}"
        )
