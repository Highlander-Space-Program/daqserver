import asyncio
import os

from fastapi import WebSocket
from server.web.app import app
import uvicorn
from dotenv import load_dotenv
from server.db.bridge import Bridge


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        data = await websocket.receive_text()
        await websocket.send_text(f"Message text was: {data}")


async def start():
    loop = asyncio.get_running_loop()
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()


def main():
    load_dotenv()
    influx_url = os.getenv("INFLUXDB_URL")
    influx_token = os.getenv("INFLUXDB_TOKEN")
    influx_database = os.getenv("INFLUXDB_DATABASE")
    mqtt_host = os.getenv("MQTT_HOST")
    mqtt_port = int(os.getenv("MQTT_PORT", 1883))
    influx_exists = all([influx_url, influx_token, influx_database, mqtt_host])

    if influx_exists:
       bridge = Bridge(influx_url, influx_token, influx_database, mqtt_host, mqtt_port)
       bridge.start()

    print(f"influx exists: {influx_exists}")

    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()

# vim: et:sw=4
