import asyncio
import os
from dataclasses import dataclass

from fastapi import WebSocket
from server.web.app import app
import uvicorn
from dotenv import load_dotenv

from server.streaming.lj import LabjackT7
# from server.streaming.sensors import load_sensors_from_json
from server.bridge import Bridge
from threading import Thread

from server.streaming.grafana_live import GrafanaLivePublisher
from server.logger import server_logger as logger
from server.pool import Datapool
from server.streaming.stream import init_streaming
from server.web.app import init_app, init_db


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")

@dataclass
class Sensor():
    stream_id: str

async def start():
    loop = asyncio.get_running_loop()

    # t7 = LabjackT7(datapool)
    # sensors = load_sensors_from_json("labjack_channels.json", board="T7")

    # thread = Thread(
    #     target=t7.stream,
    #     args=(sensors, loop),
    #     daemon=True
    # )
    # thread.start()

    await init_db()
    app = init_app()
    init_grafana_live()
    init_streaming()

    sensors = [Sensor("asdf")] * 3
    grafana_live_publishers = [GrafanaLivePublisher(stream_id=sensor.stream_id) for sensor in sensors]

    logger.info("Listening on http://localhost:8000")
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)

    try:
        await server.serve()
    finally:
        logger.info("[Shutdown] cleaning up...")
        for publisher in grafana_live_publishers:
            await publisher.close()


def main():
    load_dotenv()
    influx_url = os.getenv("INFLUXDB_URL")
    influx_token = os.getenv("INFLUXDB_TOKEN")
    influx_database = os.getenv("INFLUXDB_DATABASE")
    mqtt_host = os.getenv("MQTT_HOST")
    mqtt_port = int(os.getenv("MQTT_PORT", 1883))
    influx_exists = all([influx_url, influx_token, influx_database, mqtt_host])

    if influx_exists:
        bridge = Bridge(
            influx_url, influx_token, influx_database, mqtt_host, mqtt_port
        )
        bridge.start()

    print(f"influx exists: {influx_exists}")

    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Shutting down server")


if __name__ == "__main__":
    main()

# vim: et:sw=4
