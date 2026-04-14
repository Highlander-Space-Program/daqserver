import asyncio
import contextlib
import json
from concurrent.futures import ThreadPoolExecutor

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from labjack import ljm

from server.streaming.ljTest import LabJackT7
from server.streaming.sensors import load_sensors_from_json

# Shared state

sensor_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
executor = ThreadPoolExecutor(max_workers=1)


# Lifespan: startup -> stream -> shutdown
@contextlib.asynccontextmanager
async def lifespan(app: FastAPI):
    # --- startup ---
    sensors = load_sensors_from_json("labjack_channels.json")
    t7 = LabJackT7()

    loop = asyncio.get_event_loop()
    loop.run_in_executor(executor, t7.stream, sensors, sensor_queue, loop)

    yield  # app runs here

    # --- shutdown ---
    executor.shutdown(wait=False)
    t7.close()


# App
app = FastAPI(lifespan=lifespan)


@app.websocket("/ws/sensors")
async def sensor_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            packet = await sensor_queue.get()
            await websocket.send_text(json.dumps(packet))
    except WebSocketDisconnect:
        pass


# Entry point
if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
