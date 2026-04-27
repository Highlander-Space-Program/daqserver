from typing import Any
from uuid import uuid4
import aiosqlite

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse
from pydantic import BaseModel

from server.web.connection import ConnectionManager, ErrorMessage

app = FastAPI()
manager = ConnectionManager()

app.mount("/static", StaticFiles(directory="./server/web/static"), name="static")
templates = Jinja2Templates(directory="./server/web/templates")

DB_PATH = "daq_ui.db"

PORT_OPTIONS = [f"PT-{i}" for i in range(1, 9)] + [f"LC-{i}" for i in range(1, 9)]

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

        await db.commit()


@app.on_event("startup")
async def startup():
    await init_db()


async def get_equations_from_db():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, expression FROM equations") as cursor:
            rows = await cursor.fetchall()

    return [
        {"id": r[0], "name": r[1], "expression": r[2]}
        for r in rows
    ]


async def get_sensors_from_db():
    async with aiosqlite.connect(DB_PATH) as db:
        async with db.execute("SELECT id, name, port, equation_id FROM sensors") as cursor:
            rows = await cursor.fetchall()

    return [
        {"id": r[0], "name": r[1], "port": r[2], "equation_id": r[3]}
        for r in rows
    ]


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
    return {
        "ports": PORT_OPTIONS,
        "equations": await get_equations_from_db(),
        "sensors": await get_sensors_from_db(),
        "graphs": list(graphs.values()),
        "read_rate_hz": "--",
        "active_graphs": len(graphs),
    }


@app.post("/api/equations")
async def add_equation(payload: EquationPayload):
    eq_id = str(uuid4())

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO equations (id, name, expression) VALUES (?, ?, ?)",
            (eq_id, payload.name, payload.expression),
        )
        await db.commit()

    return {"id": eq_id, **payload.dict()}


@app.patch("/api/equations/{equation_id}")
async def edit_equation(equation_id: str, payload: EquationPayload):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE equations SET name = ?, expression = ? WHERE id = ?",
            (payload.name, payload.expression, equation_id),
        )
        await db.commit()

        if cursor.rowcount == 0:
            return {"error": "Equation not found"}

    return {"id": equation_id, **payload.dict()}


@app.delete("/api/equations/{equation_id}")
async def delete_equation(equation_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM equations WHERE id = ?",
            (equation_id,),
        )

        await db.execute(
            "UPDATE sensors SET equation_id = NULL WHERE equation_id = ?",
            (equation_id,),
        )

        await db.commit()

        if cursor.rowcount == 0:
            return {"error": "Equation not found"}

    return {"success": True}


@app.post("/api/sensors")
async def add_sensor(payload: SensorPayload):
    sensor_id = str(uuid4())

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO sensors (id, name, port, equation_id) VALUES (?, ?, ?, ?)",
            (sensor_id, payload.name, payload.port, payload.equation_id),
        )
        await db.commit()

    return {"id": sensor_id, **payload.dict()}


@app.patch("/api/sensors/{sensor_id}")
async def edit_sensor(sensor_id: str, payload: SensorPayload):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "UPDATE sensors SET name = ?, port = ?, equation_id = ? WHERE id = ?",
            (payload.name, payload.port, payload.equation_id, sensor_id),
        )
        await db.commit()

        if cursor.rowcount == 0:
            return {"error": "Sensor not found"}

    return {"id": sensor_id, **payload.dict()}


@app.delete("/api/sensors/{sensor_id}")
async def delete_sensor(sensor_id: str):
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "DELETE FROM sensors WHERE id = ?",
            (sensor_id,),
        )
        await db.commit()

        if cursor.rowcount == 0:
            return {"error": "Sensor not found"}

    to_delete = [
        gid for gid, g in graphs.items()
        if g["sensor_id"] == sensor_id
    ]
    for gid in to_delete:
        del graphs[gid]

    return {"success": True}


@app.post("/api/graphs")
async def add_graph(payload: GraphPayload):
    graph_id = str(uuid4())
    graph = {
        "id": graph_id,
        "name": payload.name,
        "sensor_id": payload.sensor_id,
    }
    graphs[graph_id] = graph
    return graph


@app.patch("/api/graphs/{graph_id}")
async def edit_graph(graph_id: str, payload: GraphPayload):
    if graph_id not in graphs:
        return {"error": "Graph not found"}

    graphs[graph_id]["name"] = payload.name
    graphs[graph_id]["sensor_id"] = payload.sensor_id
    return graphs[graph_id]


@app.delete("/api/graphs/{graph_id}")
async def delete_graph(graph_id: str):
    if graph_id not in graphs:
        return {"error": "Graph not found"}

    del graphs[graph_id]
    return {"success": True}


@app.post("/api/graphs/{graph_id}/tare")
async def tare_graph(graph_id: str):
    if graph_id not in graphs:
        return {"error": "Graph not found"}

    graphs[graph_id]["tare"] = True
    return {"success": True}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            msg: dict[str, Any] = await websocket.receive_json()

            action = msg.get("action")
            arguments = msg.get("arguments")

            if action is None or arguments is None:
                await websocket.send_json(
                    ErrorMessage("Missing action or arguments").to_dict()
                )
                return

            if action == "subscribe":
                manager.subscribe(websocket, *arguments)
            elif action == "unsubscribe":
                manager.unsubscribe(websocket, *arguments)

    except WebSocketDisconnect:
        manager.disconnect(websocket)