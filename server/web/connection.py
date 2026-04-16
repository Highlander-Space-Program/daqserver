from abc import ABC, abstractmethod
from typing import override

from fastapi import WebSocket


class Sendable(ABC):
    @abstractmethod
    def message_type(self) -> str:
        pass

    @abstractmethod
    def get_data(self) -> dict | str:
        pass

    def to_dict(self) -> dict:
        return {"message_type": self.message_type(), "data": self.get_data()}


class ErrorMessage(Sendable):
    TYPE: str = "error"

    def __init__(self, message: str) -> None:
        self.message = message

    @override
    def message_type(self) -> str:
        return self.TYPE

    @override
    def get_data(self) -> dict | str:
        return self.message


class ConnectionManager:
    def __init__(self):
        self.active_connections = {}

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections[websocket] = set()

    def disconnect(self, websocket: WebSocket):
        self.active_connections.pop(websocket, None)

    def subscribe(self, websocket: WebSocket, topic: str):
        self.active_connections[websocket].add(topic)

    def unsubscribe(self, websocket: WebSocket, topic: str):
        self.active_connections[websocket].discard(topic)

    async def broadcast(self, topic: str, data: dict):
        for ws, topics in self.active_connections.items():
            if topic in topics:
                await ws.send_json({"topic": topic, "data": data})
