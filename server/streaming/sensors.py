from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import json
from datetime import datetime
from typing import List, Optional, Self, override


class InputId(ABC):
    @abstractmethod
    def to_dict(self) -> dict:
        raise NotImplementedError

    @classmethod
    @abstractmethod
    def from_dict(cls, dictionary: dict) -> Self:
        raise NotImplementedError


@dataclass
class TestID(InputId):
    sensor_type: str = "Test"

    @override
    def to_dict(self) -> dict:
        return {"sensor_type": self.sensor_type}

    @classmethod
    @override
    def from_dict(cls, dictionary: dict) -> Self:
        _ = dictionary
        return cls()


@dataclass
class T7ID(InputId):
    mux_number: int
    cb37_pin: str
    sensor_type: str = "T7"

    @override
    def to_dict(self) -> dict:
        return {
            "mux_number": self.mux_number,
            "cb37_pin": self.cb37_pin,
            "type": self.sensor_type,
        }

    @classmethod
    @override
    def from_dict(cls, dictionary: dict) -> Self:
        return cls(dictionary["mux_number"], dictionary["cb37_pin"])


@dataclass
class T8ID(InputId):
    mux_number: int
    cb37_pin: int
    sensor_type: str = "T8"

    @override
    def to_dict(self) -> dict:
        return {
            "mux_number": self.mux_number,
            "cb37_pin": self.cb37_pin,
            "type": self.sensor_type,
        }

    @classmethod
    @override
    def from_dict(cls, dictionary: dict) -> Self:
        return cls(dictionary["mux_number"], dictionary["cb37_pin"])


class DataType(Enum):
    TC = "thermocouple"
    PT = "pressuretransducer"
    LC = "loadcell"
    TEST = "test"


@dataclass
class TimeBasedData:
    time: datetime
    value: float

    def to_dict(self) -> dict:
        return {
            "time": self.time.strftime("%Y-%m-%d %H:%M:%S.%f"),
            "value": self.value,
        }


@dataclass
class SensorOutput:
    data_type: DataType
    source: InputId
    data: list[TimeBasedData]


class SensorData(ABC):
    @abstractmethod
    def get_data(self) -> SensorOutput:
        raise NotImplementedError()

    @abstractmethod
    def to_dict(self) -> dict:
        raise NotImplementedError()

    @classmethod
    @abstractmethod
    def from_dict(cls, dictionary: dict) -> Self:
        raise NotImplementedError()


class Sensor:
    def __init__(
        self,
        ain: str,
        sensor_type: str,
        differential: bool,
        negative_ain: Optional[str] = None,
    ):
        self.ain = ain  # e.g. "AIN48"
        self.sensor_type = sensor_type
        self.differential = differential
        self.negative_ain = negative_ain  # e.g. "AIN56" or None

    def __repr__(self):
        return f"<Sensor {self.ain} | {self.sensor_type} | Diff={self.differential} | Neg={self.negative_ain}>"

    def _ain_num(self, label: str) -> int:
        if not label.startswith("AIN"):
            raise ValueError(f"Expected AIN label like 'AIN48', got '{label}'")
        return int(label.replace("AIN", ""))

    def configure_labjack(self, ljm, lj):
        """
        Configure analog input for LabJack T7.

        Supports:
        - Single-ended sensors
        - Differential sensors (load cells, TCs)
        - Thermocouples via Extended Features (EF)

        Validates:
        - Built-in T7 pairs: AIN0->AIN1 and AIN2->AIN3
        - Mux80 extended channels (48-127): negative = positive + 8
        """

        ain_num = self._ain_num(self.ain)

        # Differential
        if self.differential:
            if not self.negative_ain:
                raise ValueError(
                    f"Differential sensor {self.ain} requires 'NegativeAIN' in config."
                )

            neg_num = self._ain_num(self.negative_ain)
            valid = False

            # Built-in T7 pairs
            if ain_num in (0, 2) and neg_num == ain_num + 1:
                valid = True

            # Mux80 extended channels
            if 48 <= ain_num <= 127 and neg_num == ain_num + 8:
                valid = True

            if not valid:
                raise ValueError(
                    f"Invalid differential pair: {self.ain} and {self.negative_ain}. "
                    "Allowed: AIN0->AIN1, AIN2->AIN3, or Mux80 (AINx->AINx+8)."
                )

            ljm.eWriteName(lj.handle, f"{self.ain}_RANGE", 0.01)
            ljm.eWriteName(lj.handle, f"{self.ain}_NEGATIVE_CH", neg_num)

        else:
            # Single-ended (GND reference)
            ljm.eWriteName(lj.handle, f"{self.ain}_NEGATIVE_CH", 199)

    def read_value(self, ljm, handle):
        value = ljm.eReadName(handle, self.ain)
        print(f"{self.ain}: {value:.6f} V")
        return value


def load_sensors_from_json(
    path: str = "labjack_channels.json",
    board: str | None = None,
) -> List[Sensor]:
    try:
        with open(path, "r") as f:
            data = json.load(f)
    except Exception as e:
        print(f"Error reading {path}: {e}")
        return []

    # support wrapped format
    if isinstance(data, dict) and "Channels" in data:
        data = data["Channels"]

    sensors = []
    for entry in data:
        try:
            if board and entry.get("Board") != board:
                continue

            sensors.append(
                Sensor(
                    ain=entry["AIN"],
                    sensor_type=entry["SensorType"],
                    differential=entry.get("Differential", False),
                    negative_ain=entry.get("NegativeAIN"),
                )
            )
        except KeyError as e:
            print(f"Skipping invalid entry (missing {e}): {entry}")

    print(f"Loaded {len(sensors)} sensors")
    return sensors
