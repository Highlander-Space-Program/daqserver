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