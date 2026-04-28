from abc import ABC, abstractmethod
import asyncio
from enum import Enum
from typing import override
import inspect
from collections import defaultdict

from server.streaming.sensors import SensorData


class Topic(Enum):
    SENSORDATA = "SENSORDATA"


class DenoiseMethod(ABC):
    """
    Solutions for handling noisy sensor inputs
    """

    @abstractmethod
    def __call__(self, data) -> float: ...


class MovingAverage(DenoiseMethod):
    def __init__(self, window_size):
        self.window_size = window_size
        self.window = [0] * window_size
        self.current_index = 0

    def add(self, data):
        self.window[self.current_index] = data
        self.current_index += 1
        self.current_index %= self.window_size

    def rolling_average(self) -> float:
        """
        self explanatory
        """

        return sum(self.window) / self.window_size

    @override
    def __call__(self, data) -> float:
        self.add(data)
        return self.rolling_average()


class Ema(DenoiseMethod):
    def __init__(self, alpha=0.2) -> None:
        self.alpha = alpha
        self.previous = 0

    def ema(self, data) -> float:
        """
        Exponential moving average

        Good for real-time smoothing
        """

        current = self.alpha * data + (1 - self.alpha) * self.previous
        self.previous = current

        return current

    @override
    def __call__(self, data) -> float:
        return self.ema(data)


class Datapool:
    def __init__(self, loop: asyncio.AbstractEventLoop):
        """
        Initializes the Datapool with an active asyncio event loop.
        """
        self.loop = loop
        self.subscribers = defaultdict(set)

    def subscribe(self, topic: Topic, callback):
        """
        Registers a subscriber to a specific topic.
        The callback must be an async function.
        """
        if not inspect.iscoroutinefunction(callback):
            raise TypeError(
                f"Subscriber callback for '{topic}' must be an async function."
            )

        self.subscribers[topic.value].add(callback)

    def publish(self, topic: Topic, data: SensorData):
        """
        Synchronously publishes data to a topic.
        Schedules the async subscribers to execute on the provided event loop.
        """
        if topic.value not in self.subscribers.keys():
            return

        for callback in self.subscribers[topic.value]:
            asyncio.run_coroutine_threadsafe(callback(data), self.loop)
