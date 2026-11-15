from abc import ABC, abstractmethod
from collections import deque
from datetime import datetime
from threading import Event
from typing import Self, override
import asyncio

try:
    from labjack import ljm
except ImportError:
    ljm = None

from server.streaming.sensors import (
    PORT_OPTIONS,
    DataType,
    InputId,
    LabJackData as _UnusedLabJackData,  # Remove if not defined in sensors.py
    Sensor,
    SensorData,
    SensorOutput,
    T7ID,
    TestID,
    TimeBasedData,
)
from server.states import PIN_MAPPING
from server.logger import streaming_logger


# ---------------------------------------------------------------------
# Calibration
# ---------------------------------------------------------------------

def calibration1(voltage: float) -> float:
    return 115918.38800425902 * voltage - 3.743950002152496


def calibration2(voltage: float) -> float:
    return 120315.08079063638 * voltage - 4.1362754116597245


def calibration3(voltage: float) -> float:
    return 118278.07807607231 * voltage + 6.439642411975598


def thermocouple_voltage_to_celsius(
    voltage: float,
    cj_temp_c: float = 25.0,
) -> float:
    return cj_temp_c + voltage / 0.000041


def loadcell_voltage_to_lbs(voltage: float) -> float:
    return ((-0.4995 * (voltage * 1e5)) + 0.8905) * 2.20462


def pressure_voltage_to_psi(voltage: float) -> float:
    return ((voltage - 0.5) / 4.0) * 1600


def loadcell_voltage_to_lbs_formula(
    voltage: float,
    rated_capacity_kg: float,
    rated_output_mv_per_v: float,
    excitation_voltage: float,
    zero_offset_v: float = 0.0,
) -> float:
    full_scale_voltage = (
        rated_output_mv_per_v / 1000.0
    ) * excitation_voltage

    net_voltage = voltage - zero_offset_v
    load_kg = (net_voltage / full_scale_voltage) * rated_capacity_kg

    return load_kg * 2.20462


# ---------------------------------------------------------------------
# Sensor data wrapper
# ---------------------------------------------------------------------

class LabJackData(SensorData):
    def __init__(
        self,
        input_id: InputId,
        data_type: DataType,
        value: float,
        timestamp: datetime | None = None,
    ):
        self.data = TimeBasedData(timestamp or datetime.now(), value)
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


# ---------------------------------------------------------------------
# Acquisition base class
# ---------------------------------------------------------------------

class Labjack(ABC):
    SCAN_RATE_HZ = 10
    SCANS_PER_READ = 1

    SMOOTHING_WINDOWS = {
        "thermocouple": 10,
        "tc": 10,
        "load_cell": 50,
        "loadcell": 50,
        "lc": 50,
        "pressure": 20,
        "pt": 20,
    }

    def __init__(
        self,
        manager=None,
        loop=None,
        ljm_api=None,
        on_sensor_data=None,
        warmup_reads: int = 50,
    ) -> None:
        self.handle = None
        self.manager = manager
        self.loop = loop
        self.ljm = ljm_api if ljm_api is not None else ljm
        self.on_sensor_data = on_sensor_data
        self.warmup_reads = warmup_reads

        self._buffers: dict[str, deque] = {}
        self._tare: dict[str, float] = {}

        self.device = "UNKNOWN"
        self._stop_event = Event()

        if self.ljm is None:
            raise RuntimeError(
                "LabJack LJM is unavailable. "
                "Use the virtual backend or install LabJack LJM."
            )

    @abstractmethod
    def open(
        self,
        connection_type: str = "ANY",
        identifier: str = "ANY",
    ) -> None:
        raise NotImplementedError

    def stop(self) -> None:
        self._stop_event.set()

    def close(self) -> None:
        self.stop()

        if self.handle is not None:
            try:
                self.ljm.close(self.handle)
            finally:
                self.handle = None

        print("LabJack closed.")

    # -----------------------------------------------------------------
    # Smoothing and tare
    # -----------------------------------------------------------------

    def _smooth(
        self,
        ain: str,
        value: float,
        sensor_type: str = "",
    ) -> float:
        window = self.SMOOTHING_WINDOWS.get(
            sensor_type.lower(),
            25,
        )

        if ain not in self._buffers:
            self._buffers[ain] = deque(
                [value] * window,
                maxlen=window,
            )

        self._buffers[ain].append(value)

        average = sum(self._buffers[ain]) / len(self._buffers[ain])

        return average - self._tare.get(ain, 0.0)

    def tare(
        self,
        sensor_type_by_ain: dict[str, str],
        ain: str = "",
    ) -> None:
        if ain:
            if ain in self._buffers:
                self._tare[ain] = (
                    sum(self._buffers[ain]) / len(self._buffers[ain])
                )
                print(f"Tared {ain}: {self._tare[ain]:.4f}")
            return

        for channel, buffer in self._buffers.items():
            sensor_type = sensor_type_by_ain.get(channel, "").lower()

            if sensor_type in ("loadcell", "load_cell", "lc"):
                self._tare[channel] = sum(buffer) / len(buffer)
                print(f"Tared {channel}: {self._tare[channel]:.4f}")

    # -----------------------------------------------------------------
    # LJM stream setup
    # -----------------------------------------------------------------

    def _build_scan_list(self, sensors: list[Sensor]):
        channel_names = [sensor.ain for sensor in sensors]

        addresses, _ = self.ljm.namesToAddresses(
            len(channel_names),
            channel_names,
        )

        print("Scan list:")
        for name, address in zip(channel_names, addresses):
            print(f"  {name} -> {address}")

        return addresses, channel_names

    def _start_stream(
        self,
        scan_list: list,
        num_channels: int,
    ) -> float:
        self.ljm.eWriteName(
            self.handle,
            "STREAM_RESOLUTION_INDEX",
            0,
        )
        self.ljm.eWriteName(
            self.handle,
            "STREAM_SETTLING_US",
            100,
        )

        settling = self.ljm.eReadName(
            self.handle,
            "STREAM_SETTLING_US",
        )
        print(f"Settling time: {settling} µs")

        actual_rate = self.ljm.eStreamStart(
            self.handle,
            self.SCANS_PER_READ,
            num_channels,
            scan_list,
            self.SCAN_RATE_HZ,
        )

        print(f"Stream started at {actual_rate:.1f} Hz")
        return actual_rate

    # -----------------------------------------------------------------
    # Conversion
    # -----------------------------------------------------------------

    @staticmethod
    def _convert(
        voltage: float,
        sensor_type: str,
        ain: str,
    ) -> float:
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

            return loadcell_voltage_to_lbs_formula(
                voltage,
                rated_capacity_kg=500,
                rated_output_mv_per_v=2,
                excitation_voltage=5,
            )

        if sensor_type in ("pressure", "pt"):
            return pressure_voltage_to_psi(voltage)

        return voltage

    # -----------------------------------------------------------------
    # Implicit topic mapping
    # -----------------------------------------------------------------

    @staticmethod
    def _data_type_for_sensor(sensor_type: str) -> DataType:
        sensor_type = (sensor_type or "").lower()

        if sensor_type in ("thermocouple", "tc"):
            return DataType.TC

        if sensor_type in ("pressure", "pt"):
            return DataType.PT

        if sensor_type in ("loadcell", "load_cell", "lc"):
            return DataType.LC

        return DataType.TEST

    @staticmethod
    def _find_topic(
        input_id: T7ID,
        data_type: DataType,
    ) -> str | None:
        """
        Preserve PORT_OPTIONS implicit mapping, but disambiguate
        duplicate T7ID values using the sensor's DataType.
        """
        prefixes = {
            DataType.TC: ("TC",),
            DataType.PT: ("PT",),
            DataType.LC: ("LC",),
            DataType.TEST: ("TEST",),
        }

        for topic, configured_input in PORT_OPTIONS.items():
            if configured_input != input_id:
                continue

            if topic.upper().startswith(prefixes[data_type]):
                return topic

        return None

    # -----------------------------------------------------------------
    # Publishing
    # -----------------------------------------------------------------

    def _emit(self, sensor_data: LabJackData) -> None:
        output = sensor_data.get_data()

        # Main publishing callback. This is independent of the UI.
        if self.on_sensor_data is not None:
            try:
                self.on_sensor_data(output)
            except Exception:
                streaming_logger.exception(
                    "Failed to publish sensor output."
                )

        # Optional existing FastAPI/UI broadcast.
        topic = self._find_topic(
            sensor_data.input_id,
            sensor_data.data_type,
        )

        if topic is not None and self.manager is not None and self.loop is not None:
            try:
                future = asyncio.run_coroutine_threadsafe(
                    self.manager.broadcast(topic, sensor_data),
                    self.loop,
                )
                future.add_done_callback(self._log_broadcast_error)
            except Exception:
                streaming_logger.exception(
                    "Failed to schedule UI broadcast."
                )

    @staticmethod
    def _log_broadcast_error(future) -> None:
        try:
            future.result()
        except Exception:
            streaming_logger.exception("UI broadcast failed.")

    # -----------------------------------------------------------------
    # Acquisition loop
    # -----------------------------------------------------------------

    def stream(
        self,
        sensors: list[Sensor],
        stop_event: Event | None = None,
    ) -> None:
        if not sensors:
            raise ValueError("No sensors were provided to the DAQ.")

        stop_event = stop_event or self._stop_event

        for sensor in sensors:
            sensor.configure_labjack(self.ljm, self)

        scan_list, channel_names = self._build_scan_list(sensors)
        num_channels = len(channel_names)

        sensor_type_by_ain = {
            sensor.ain: sensor.sensor_type
            for sensor in sensors
        }

        self._start_stream(scan_list, num_channels)

        try:
            # Warmup readings seed the rolling averages.
            for _ in range(self.warmup_reads):
                if stop_event.is_set():
                    return

                data, _, _ = self.ljm.eStreamRead(self.handle)

                for channel_index, ain in enumerate(channel_names):
                    raw_voltage = data[channel_index]
                    sensor_type = sensor_type_by_ain[ain]

                    converted = self._convert(
                        raw_voltage,
                        sensor_type,
                        ain,
                    )
                    self._smooth(ain, converted, sensor_type)

            print("Streaming. Press Ctrl+C to stop.")

            while not stop_event.is_set():
                data, device_backlog, ljm_backlog = (
                    self.ljm.eStreamRead(self.handle)
                )

                scans = len(data) // num_channels

                for scan_index in range(scans):
                    timestamp = datetime.now()
                    base = scan_index * num_channels

                    for channel_index, ain in enumerate(channel_names):
                        raw_voltage = data[base + channel_index]
                        sensor_type = sensor_type_by_ain[ain]

                        value = self._convert(
                            raw_voltage,
                            sensor_type,
                            ain,
                        )
                        value = self._smooth(
                            ain,
                            value,
                            sensor_type,
                        )

                        mapping = PIN_MAPPING.get(ain)
                        if mapping is None:
                            streaming_logger.warning(
                                "No PIN_MAPPING entry for %s; skipping.",
                                ain,
                            )
                            continue

                        input_id = T7ID(
                            mux_number=mapping["mux"],
                            cb37_pin=mapping["cb37_pin"],
                        )

                        data_type = self._data_type_for_sensor(
                            sensor_type
                        )

                        sensor_data = LabJackData(
                            input_id,
                            data_type,
                            value,
                            timestamp,
                        )

                        self._emit(sensor_data)

        except KeyboardInterrupt:
            print("Stream interrupted.")

        finally:
            try:
                self.ljm.eStreamStop(self.handle)
            except Exception:
                streaming_logger.exception(
                    "Failed to stop LabJack stream."
                )

            print("Stream stopped.")


# ---------------------------------------------------------------------
# Device implementations
# ---------------------------------------------------------------------

class LabjackT7(Labjack):
    def __init__(
        self,
        manager=None,
        loop=None,
        ljm_api=None,
        on_sensor_data=None,
        warmup_reads: int = 50,
    ):
        super().__init__(
            manager=manager,
            loop=loop,
            ljm_api=ljm_api,
            on_sensor_data=on_sensor_data,
            warmup_reads=warmup_reads,
        )
        self.device = "T7"

    @override
    def open(
        self,
        connection_type: str = "ANY",
        identifier: str = "ANY",
    ) -> None:
        print(f"Opening T7 over {connection_type}...")

        self.handle = self.ljm.openS(
            "T7",
            connection_type,
            identifier,
        )

        try:
            self.ljm.eStreamStop(self.handle)
        except Exception as error:
            streaming_logger.debug(str(error))

        info = self.ljm.getHandleInfo(self.handle)

        print(
            f"Opened T7 — device: {info[0]}, "
            f"connection: {info[1]}, serial: {info[2]}, IP: {info[3]}"
        )


class LabjackT8(Labjack):
    def __init__(
        self,
        manager=None,
        loop=None,
        ljm_api=None,
        on_sensor_data=None,
        warmup_reads: int = 50,
    ):
        super().__init__(
            manager=manager,
            loop=loop,
            ljm_api=ljm_api,
            on_sensor_data=on_sensor_data,
            warmup_reads=warmup_reads,
        )
        self.device = "T8"

    @override
    def open(
        self,
        connection_type: str = "ANY",
        identifier: str = "ANY",
    ) -> None:
        print(f"Opening T8 over {connection_type}...")

        self.handle = self.ljm.openS(
            "T8",
            connection_type,
            identifier,
        )

        try:
            self.ljm.eStreamStop(self.handle)
        except Exception as error:
            streaming_logger.debug(str(error))

        info = self.ljm.getHandleInfo(self.handle)

        print(
            f"Opened T8 — device: {info[0]}, "
            f"connection: {info[1]}, serial: {info[2]}, IP: {info[3]}"
        )


