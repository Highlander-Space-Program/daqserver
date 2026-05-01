from fastapi.templating import Jinja2Templates

from server.states import PORT_OPTIONS
from server.streaming.sensors import SensorData
from server.web.connection import ConnectionManager


templates = Jinja2Templates(directory="./server/web/templates")
manager = ConnectionManager()


async def pass_to_frontend(sensor_data: SensorData):
    data = sensor_data.get_data()

    topic = None
    for destination, source in PORT_OPTIONS.items():
        if source == data.source:
            topic = destination

    if topic is not None:
        await manager.broadcast(topic, sensor_data)
