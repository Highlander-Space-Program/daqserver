import math
import random
import re
import time


class VirtualLabJack:
    """
    Minimal LJM-compatible API for exercising Labjack.stream().

    Supported modes:
      normal   - stable, realistic values
      constant - fixed values
      ramp     - slowly increasing engineering values
      noise    - values with added noise
      missing  - one channel returns NaN
      invalid  - one channel returns infinity
    """

    def __init__(
        self,
        sensors,
        mode="normal",
        scan_rate_hz=10,
        seed=42,
    ):
        self.sensors = sensors
        self.mode = mode.lower()
        self.scan_rate_hz = scan_rate_hz
        self.random = random.Random(seed)

        self.handle = 1
        self.streaming = False
        self.scan_list = []
        self.channel_names = []
        self.sensor_types = {}

        self.write_history = {}
        self.read_count = 0
        self.start_time = time.monotonic()

        for sensor in sensors:
            self.sensor_types[sensor.ain] = sensor.sensor_type.lower()

    # ---------------------------------------------------------------
    # Device API
    # ---------------------------------------------------------------

    def openS(self, device_type, connection_type, identifier):
        return self.handle

    def close(self, handle):
        self.streaming = False

    def getHandleInfo(self, handle):
        return (
            7,          # device type
            1,          # connection type
            123456,     # serial number
            0x7F000001, # IP address placeholder
            0,
            0,
        )

    def namesToAddresses(self, num_names, names):
        addresses = []

        for name in names:
            match = re.fullmatch(r"AIN(\d+)", name)
            if match:
                addresses.append(int(match.group(1)))
            else:
                addresses.append(abs(hash(name)) % 10000)

        self.channel_names = list(names)
        return addresses, [0] * num_names

    def eWriteName(self, handle, name, value):
        self.write_history[name] = value

    def eReadName(self, handle, name):
        return self.write_history.get(name, 0)

    def eStreamStart(
        self,
        handle,
        scans_per_read,
        num_channels,
        scan_list,
        scan_rate,
    ):
        self.scan_list = list(scan_list)
        self.streaming = True
        self.scan_rate_hz = scan_rate
        self.start_time = time.monotonic()
        return scan_rate

    def eStreamStop(self, handle):
        self.streaming = False

    # ---------------------------------------------------------------
    # Engineering-value profiles
    # ---------------------------------------------------------------

    def _target_value(self, ain, sensor_type):
        elapsed = time.monotonic() - self.start_time

        if sensor_type in ("pressure", "pt"):
            base = {
                "AIN80": 500.0,
                "AIN81": 750.0,
            }.get(ain, 400.0)

        elif sensor_type in ("loadcell", "load_cell", "lc"):
            base = 100.0

        elif sensor_type in ("thermocouple", "tc"):
            base = 35.0

        else:
            base = 1.0

        if self.mode == "ramp":
            return base + (elapsed * 2.0)

        return base

    def _engineering_value_to_voltage(self, value, sensor_type):
        if sensor_type in ("pressure", "pt"):
            return (value / 1600.0) * 4.0 + 0.5

        if sensor_type in ("thermocouple", "tc"):
            return (value - 25.0) * 0.000041

        if sensor_type in ("loadcell", "load_cell", "lc"):
            # Matches the fallback conversion in lj.py:
            # 500 kg capacity, 2 mV/V, 5 V excitation.
            load_kg = value / 2.20462
            full_scale_voltage = (2.0 / 1000.0) * 5.0
            return (load_kg / 500.0) * full_scale_voltage

        return value

    def _read_channel(self, ain):
        sensor_type = self.sensor_types.get(ain, "")
        value = self._target_value(ain, sensor_type)

        if self.mode == "noise":
            value += self.random.gauss(0, 1.0)

        voltage = self._engineering_value_to_voltage(
            value,
            sensor_type,
        )

        if self.mode == "missing" and ain == self.channel_names[0]:
            return float("nan")

        if self.mode == "invalid" and ain == self.channel_names[0]:
            return float("inf")

        if self.mode == "noise":
            voltage += self.random.gauss(0, 0.0001)

        return voltage

    # ---------------------------------------------------------------
    # Stream API
    # ---------------------------------------------------------------

    def eStreamRead(self, handle):
        if not self.streaming:
            raise RuntimeError("Virtual stream has not been started.")

        time.sleep(1.0 / self.scan_rate_hz)

        self.read_count += 1

        values = [
            self._read_channel(ain)
            for ain in self.channel_names
        ]

        return values, 0, 0
