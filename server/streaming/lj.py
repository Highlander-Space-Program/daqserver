from abc import ABC, abstractmethod
import random
from threading import Thread
import time
from datetime import datetime
from typing import Self, override
from collections import deque
from labjack import ljm
from server.streaming.sensors import Sensor
from server.pool import Datapool, Topic
from server.streaming.sensors import (
    DataType,
    InputId,
    SensorData,
    SensorOutput,
    TestID,
    TimeBasedData,
)
from server.streaming.sensors import T7ID
from server.logger import streaming_logger
from server.states import PIN_MAPPING


def calibration1(voltage):
    return 115918.38800425902 * voltage + -3.743950002152496


def calibration2(voltage):
    return 120315.08079063638 * voltage + -4.1362754116597245


def calibration3(voltage):
    return 118278.07807607231 * voltage + 6.439642411975598


class LabJackData(SensorData):
    def __init__(self, input_id: InputId, data_type: DataType, value: float):
        self.data = TimeBasedData(datetime.now(), value)
        self.data_type = data_type
        self.input_id = input_id

    @override
    def get_data(self) -> SensorOutput:
        return SensorOutput(
            self.data_type,
            self.input_id,
            [self.data],
        )

    @override
    def to_dict(self) -> dict:
        return {
            "data_type": self.data_type.value,
            "input_id": self.input_id.to_dict(),
            "data": self.data.to_dict(),
        }

    @classmethod
    @override
    def from_dict(cls, dictionary: dict) -> Self:
        raise NotImplementedError()


class LabJackTest:
    def __init__(self, datapool: Datapool):
        self.datapool = datapool
        self.input_id = TestID()

    def init(self):
        t = Thread(target=self.start_stream, daemon=True)
        t.start()

    def start_stream(self):
        while True:
            value = random.random()
            fake_data = LabJackData(self.input_id, DataType.TEST, value)
            self.datapool.publish(Topic.SENSORDATA, fake_data)
            time.sleep(0.1)


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
class Labjack(ABC):
    SCAN_RATE_HZ: int = 10
    SCANS_PER_READ: int = 1

    def __init__(self, datapool: Datapool) -> None:
        self.handle = None
        self.datapool = datapool
        self._buffers: dict[str, deque] = {}
        self._tare: dict[str, float] = {}
        self.device = "UNKNOWN"

    # Connection
    @abstractmethod
    def open(self, connection_type: str = "ANY", identifier: str = "ANY") -> None:
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
    def tare(self, sensor_type_by_ain: dict[str, str], ain: str = "") -> None:
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

    def not_blocking_streaming(self):
        raise NotImplementedError

    # Streaming -> datapool
    def stream(
        self,
        sensors: list[Sensor],
    ) -> None:
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

                for scan_idx in range(scans):
                    base = scan_idx * num_channels

                    for ch_idx, ain in enumerate(channel_names):
                        raw_voltage = data[base + ch_idx]
                        sensor_type = sensor_type_by_ain.get(ain, "")

                        # convert + smooth
                        value = self._convert(raw_voltage, sensor_type, ain)
                        value = self._smooth(ain, value, sensor_type)

                        # MUX logic (important)

                        d = PIN_MAPPING[ain]
                        input_id = T7ID(
                            mux_number=d["mux"], cb37_pin=d["cb37_pin"]
                        )

                        st = sensor_type.lower()
                        if st in ("thermocouple", "tc"):
                            data_type = DataType.TC
                        elif st in ("pressure", "pt"):
                            data_type = DataType.PT
                        elif st in ("loadcell", "lc"):
                            data_type = DataType.LC
                        else:
                            data_type = DataType.TEST

                        sensor_data = LabJackData(input_id, data_type, value)

                        self.datapool.publish(Topic.SENSORDATA, sensor_data)

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
            else:
                return loadcell_voltage_to_lbs_formula(voltage, 500, 2, 5)
        if sensor_type in ("pressure", "pt"):
            return pressure_voltage_to_psi(voltage)
        return voltage  # raw voltage fallback


class LabjackT8(Labjack):
    def __init__(self, datapool: Datapool) -> None:
        super().__init__(datapool)
        self.device = "T8"

    @override
    def open(self, connection_type: str = "ANY", identifier: str = "ANY") -> None:
        print(f"Opening T8 over {connection_type}...")
        self.handle = ljm.openS("T8", connection_type, identifier)
        ljm.eStreamStop(self.handle)

        info = ljm.getHandleInfo(self.handle)
        print(
            f"Opened T8 — device: {info[0]}, connection: {info[1]}, "
            f"serial: {info[2]}, IP: {info[3]}"
        )


class LabjackT7(Labjack):
    def __init__(self, datapool: Datapool) -> None:
        super().__init__(datapool)
        self.device = "T7"

    @override
    def open(self, connection_type: str = "ANY", identifier: str = "ANY") -> None:
        print(f"Opening T7 over {connection_type}...")
        self.handle = ljm.openS("T7", connection_type, identifier)
        try:
            ljm.eStreamStop(self.handle)
        except ljm.LJMError as e:
            streaming_logger.debug(str(e))

        print("LabJack state reset.")

        info = ljm.getHandleInfo(self.handle)
        print(
            f"Opened T7 — device: {info[0]}, connection: {info[1]}, "
            f"serial: {info[2]}, IP: {info[3]}"
        )
