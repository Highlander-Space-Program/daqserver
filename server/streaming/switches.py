from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import override
import asyncio

try:
    from labjack import ljm
except ImportError:
    ljm = None

from server.states import SWITCH_MAPPING

type LabjackHandle = int


# based on https://support.labjack.com/docs/appendix-c-pinout-info
@dataclass
class SwitchID:
    switch_number: int
    psu_input: int

    def __str__(self) -> str:
        for value, pair in SWITCH_MAPPING.items():
            if (pair["switch"], pair["psu"]) == (
                f"S{self.switch_number}",
                f"P{self.psu_input}",
            ):
                return value

        raise RuntimeError("Unreachable code reached")

    def switch(self):
        return f"S{self.switch_number}"


SWITCH_OPTIONS: dict[str, SwitchID] = {
    "S0": SwitchID(0, 1),
    "S1": SwitchID(1, 1),
    "S2": SwitchID(2, 1),
    "S3": SwitchID(3, 1),
    "S4": SwitchID(4, 1),
}

GLOBAL_SWITCH_STATES: dict[str, bool] = {
    key: False for key in SWITCH_OPTIONS.keys()
}

class CommandExecutor:
    def __init__(self, handle, ljm_api=None):
        self.handle = handle
        self.ljm = ljm_api if ljm_api is not None else ljm

        if self.ljm is None:
            raise RuntimeError("LabJack LJM API is not available.")

        self._lock = asyncio.Lock()

    async def listen_for_commands(self, commands):
        async with self._lock:
            for command in commands:
                await command.execute(self.handle, self.ljm)

class Command(ABC):
    @abstractmethod
    async def execute(self, handle, ljm_api):
        raise NotImplementedError


class Start(Command):
    def __init__(self, id: SwitchID) -> None:
        self.switch_id = id

    @override
    async def execute(self, handle, ljm_api):
        ljm_api.eWriteName(handle, str(self.switch_id), 1)
        GLOBAL_SWITCH_STATES[self.switch_id.switch()] = True


class Stop(Command):
    def __init__(self, id: SwitchID) -> None:
        self.switch_id = id

    @override
    async def execute(self, handle, ljm_api):
        ljm_api.eWriteName(handle, str(self.switch_id), 0)
        GLOBAL_SWITCH_STATES[self.switch_id.switch()] = False


class Timeout(Command):
    # in seconds
    def __init__(self, duration: float) -> None:
        self.duration = duration

    @override
    async def execute(self, handle, ljm_api):
        await asyncio.sleep(self.duration)


