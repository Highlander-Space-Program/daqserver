import asyncio
import contextlib
import json
from concurrent.futures import ThreadPoolExecutor
from server.pool import Datapool, Topic

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from labjack import ljm

from lj import LabjackT7, LabjackT8
from sensors import load_sensors_from_json
from threading import Thread

# Shared state

executor = ThreadPoolExecutor(max_workers=1)


# Lifespan: startup -> stream -> shutdown
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    t7_sensors = load_sensors_from_json("labjack_channels.json", board="T7")
    # t8_sensors = load_sensors_from_json("labjack_channels.json", board="T8")

    loop = asyncio.get_event_loop()
    datapool = Datapool(loop)

    app.state.datapool = datapool

    t7 = LabjackT7(datapool)
    # t8 = LabjackT8(datapool)

    thread_t7 = Thread(target=t7.stream, args=(t7_sensors, loop), daemon=True)

    # thread_t8 = Thread(
    #     target=t8.stream,
    #     args=(t8_sensors, loop),
    #     daemon=True
    # )

    thread_t7.start()
    # thread_t8.start()

    yield  # app runs here

    # --- shutdown ---
    executor.shutdown(wait=False)
    t7.close()
    # t8.close()


# App
app = FastAPI(lifespan=lifespan)


@app.websocket("/ws/sensors")
async def sensor_ws(websocket: WebSocket):
    await websocket.accept()

    async def send_data(packet):
        try:
            await websocket.send_text(json.dumps(packet))
        except RuntimeError:
            pass  # socket closed

    # Subscribe this client to sensor data
    app.state.datapool.subscribe(Topic.SENSORDATA, send_data)

    try:
        while True:
            await asyncio.sleep(1)  # keep connection alive
    except WebSocketDisconnect:
        pass


# Entry point
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
