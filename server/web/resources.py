from fastapi import Request
from fastapi.templating import Jinja2Templates

from server.streaming.sensors import PORT_OPTIONS, SensorData
from server.web.connection import ConnectionManager


templates = Jinja2Templates(directory="./server/web/templates")
manager = ConnectionManager()


def get_datapool(request: Request):
    return request.app.state.datapool


async def pass_to_frontend(sensor_data: SensorData):
    data = sensor_data.get_data()

    topic = None
    for destination, source in PORT_OPTIONS.items():
        if source == data.source:
            topic = destination

    if topic is not None:
        await manager.broadcast(topic, sensor_data)
