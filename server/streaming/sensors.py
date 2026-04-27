from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
from datetime import datetime
from typing import Self, override


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
    ain: int
    sensor_type: str = "T7"

    @override
    def to_dict(self) -> dict:
        return {
            "mux_number": self.mux_number,
            "ain": self.ain,
            "type": self.sensor_type,
        }

    @classmethod
    @override
    def from_dict(cls, dictionary: dict) -> Self:
        return cls(dictionary["mux_number"], dictionary["ain"])


@dataclass
class T8ID(InputId):
    mux_number: int
    ain: int
    sensor_type: str = "T8"

    @override
    def to_dict(self) -> dict:
        return {
            "mux_number": self.mux_number,
            "ain": self.ain,
            "type": self.sensor_type,
        }

    @classmethod
    @override
    def from_dict(cls, dictionary: dict) -> Self:
        return cls(dictionary["mux_number"], dictionary["ain"])


class DataType(Enum):
    TC = "thermocouple"
    PT = "pressuretransducer"
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
        negative_ain: str | None = None,
    ):
        self.ain = ain
        self.sensor_type = sensor_type
        self.differential = differential
        self.negative_ain = negative_ain

    def __repr__(self):
        return (
            f"<Sensor {self.ain} | {self.sensor_type} | "
            f"Diff={self.differential} | Neg={self.negative_ain}>"
        )

    def _ain_num(self, label: str) -> int:
        if not label.startswith("AIN"):
            raise ValueError(f"Expected AIN label like 'AIN48', got '{label}'")
        return int(label.replace("AIN", ""))

    def configure_labjack(self, ljm, lj):
        ain_num = self._ain_num(self.ain)

        if self.differential:
            if not self.negative_ain:
                raise ValueError(
                    f"Differential sensor {self.ain} requires negative_ain."
                )

            neg_num = self._ain_num(self.negative_ain)

            valid = False

            if ain_num in (0, 2) and neg_num == ain_num + 1:
                valid = True

            if 48 <= ain_num <= 127 and neg_num == ain_num + 8:
                valid = True

            if not valid:
                raise ValueError(
                    f"Invalid differential pair: {self.ain} and {self.negative_ain}"
                )

            ljm.eWriteName(lj.handle, f"{self.ain}_RANGE", 0.01)
            ljm.eWriteName(lj.handle, f"{self.ain}_NEGATIVE_CH", neg_num)

        else:
            ljm.eWriteName(lj.handle, f"{self.ain}_NEGATIVE_CH", 199)

    def read_value(self, ljm, handle):
        value = ljm.eReadName(handle, self.ain)
        print(f"{self.ain}: {value:.6f} V")
        return value