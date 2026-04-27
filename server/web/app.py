from typing import Any
from uuid import uuid4
import aiosqlite
import asyncio
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse
from pydantic import BaseModel

from server.web.connection import ConnectionManager, ErrorMessage
from server.streaming.sensors import T7ID, InputId, SensorData, TestID
from server.pool import Datapool, Topic

app = FastAPI()
manager = ConnectionManager()
app.mount("/static", StaticFiles(directory="./server/web/static"), name="static")
templates = Jinja2Templates(directory="./server/web/templates")
datapool = Datapool(asyncio.new_event_loop())

PORT_OPTIONS: dict[str, InputId] = {
    "PT-1": T7ID(0, 52),
    "PT-2": T7ID(1, 60),
    "PT-3": T7ID(0, 48),
    "TC-1": T7ID(0, 50),
    "TC-2": T7ID(4, 10),
    "TC-3": T7ID(4, 10),
    "test": TestID(),
}

DB_PATH = "daq_ui.db"

sensors: dict[str, dict[str, Any]] = {}
graphs: dict[str, dict[str, Any]] = {}


class EquationPayload(BaseModel):
    name: str
    expression: str


class SensorPayload(BaseModel):
    name: str
    port: str
    equation_id: str | None = None


class GraphPayload(BaseModel):
    name: str
    sensor_id: str


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS equations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                expression TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                port TEXT NOT NULL,
                equation_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS graphs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sensor_id TEXT NOT NULL
            )
        """)

        await db.commit()


async def get_equations_from_db():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, name, expression FROM equations"
        ) as cursor:
            rows = await cursor.fetchall()

    return [{"id": row[0], "name": row[1], "expression": row[2]} for row in rows]


async def get_sensors_from_db():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute(
            "SELECT id, name, port, equation_id FROM sensors"
        ) as cursor:
            rows = await cursor.fetchall()

    return [
        {
            "id": row[0],
            "name": row[1],
            "port": row[2],
            "equation_id": row[3],
        }
        for row in rows
    ]


async def get_graphs_from_db():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, sensor_id FROM graphs") as cursor:
            rows = await cursor.fetchall()
    return [{"id": row[0], "name": row[1], "sensor_id": row[2]} for row in rows]


async def callback(sensor_data: SensorData):
    data = sensor_data.get_data()

    

    topic = None
    for destination, source in PORT_OPTIONS.items():
        if source == data.source:
            topic = destination

    if topic is not None:
        await manager.broadcast(topic, sensor_data)


@app.on_event("startup")
async def startup():
    await init_db()
    datapool.subscribe(Topic.SENSORDATA, callback)


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/controls", response_class=HTMLResponse)
async def controls_page(request: Request):
    return templates.TemplateResponse("controls.html", {"request": request})


@app.get("/cameras", response_class=HTMLResponse)
async def cameras_page(request: Request):
    return templates.TemplateResponse("cameras.html", {"request": request})


@app.get("/api/config")
async def api_config():
    graphs_list = await get_graphs_from_db()
    return {
        "ports": list(PORT_OPTIONS.keys()),
        "equations": await get_equations_from_db(),
        "sensors": await get_sensors_from_db(),
        "graphs": graphs_list,
        "read_rate_hz": "--",
        "active_graphs": len(graphs_list),
    }


@app.post("/api/equations")
async def add_equation(payload: EquationPayload):
    eq_id = str(uuid4())

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO equations (id, name, expression)
            VALUES (?, ?, ?)
            """,
            (eq_id, payload.name, payload.expression),
        )
        await db.commit()

    return {
        "id": eq_id,
        "name": payload.name,
        "expression": payload.expression,
    }


@app.patch("/api/equations/{equation_id}")
async def edit_equation(equation_id: str, payload: EquationPayload):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE equations
            SET name = ?, expression = ?
            WHERE id = ?
            """,
            (payload.name, payload.expression, equation_id),
        )

        await db.commit()

        if cursor.rowcount == 0:
            return {"error": "Equation not found"}

    return {
        "id": equation_id,
        "name": payload.name,
        "expression": payload.expression,
    }


@app.post("/api/sensors")
async def add_sensor(payload: SensorPayload):
    sensor_id = str(uuid4())

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO sensors (id, name, port, equation_id)
            VALUES (?, ?, ?, ?)
            """,
            (sensor_id, payload.name, payload.port, payload.equation_id),
        )
        await db.commit()

    return {
        "id": sensor_id,
        "name": payload.name,
        "port": payload.port,
        "equation_id": payload.equation_id,
    }


@app.patch("/api/sensors/{sensor_id}")
async def edit_sensor(sensor_id: str, payload: SensorPayload):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            """
            UPDATE sensors
            SET name = ?, port = ?, equation_id = ?
            WHERE id = ?
            """,
            (payload.name, payload.port, payload.equation_id, sensor_id),
        )

        await db.commit()

        if cursor.rowcount == 0:
            return {"error": "Sensor not found"}

    return {
        "id": sensor_id,
        "name": payload.name,
        "port": payload.port,
        "equation_id": payload.equation_id,
    }


@app.post("/api/graphs")
async def add_graph(payload: GraphPayload):
    graph_id = str(uuid4())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO graphs (id, name, sensor_id)
            VALUES (?, ?, ?)
            """,
            (graph_id, payload.name, payload.sensor_id),
        )
        await db.commit()

    return {
        "id": graph_id,
        "name": payload.name,
        "sensor_id": payload.sensor_id,
    }


@app.get("/api/latest")
def api_latest():
    return {
        "read_rate_hz": "--",
        "active_graphs": len(graphs),
        "values": {},
    }


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            msg: dict[str, Any] = await websocket.receive_json()

            action: str | None = msg.get("action")
            arguments: list[str] | None = msg.get("arguments")

            if action is None or arguments is None:
                await websocket.send_json(
                    ErrorMessage(
                        "You need to specify which action you want to perform and the arguments for that action"
                    ).to_dict()
                )
                return

            # TODO: argument counts need to be checked
            if action == "subscribe":
                print(arguments)
                breakpoint()
                manager.subscribe(websocket, *arguments)
            elif action == "unsubscribe":
                manager.unsubscribe(websocket, *arguments)

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@app.delete("/api/equations/{equation_id}")
async def delete_equation(equation_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM equations WHERE id = ?",
            (equation_id,),
        )

        await db.execute(
            """
            UPDATE sensors
            SET equation_id = NULL
            WHERE equation_id = ?
            """,
            (equation_id,),
        )

        await db.commit()

        if cursor.rowcount == 0:
            return {"error": "Equation not found"}

    return {"success": True, "id": equation_id}


@app.delete("/api/sensors/{sensor_id}")
async def delete_sensor(sensor_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM sensors WHERE id = ?",
            (sensor_id,),
        )
        # Delete connected graphs from DB
        await db.execute(
            "DELETE FROM graphs WHERE sensor_id = ?",
            (sensor_id,),
        )
        await db.commit()

        if cursor.rowcount == 0:
            return {"error": "Sensor not found"}

    # Also delete graphs connected to this sensor
    graphs_to_delete = [
        graph_id
        for graph_id, graph in graphs.items()
        if graph["sensor_id"] == sensor_id
    ]

    for graph_id in graphs_to_delete:
        del graphs[graph_id]

    return {"success": True, "id": sensor_id}
