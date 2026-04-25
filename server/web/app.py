from typing import Any
from uuid import uuid4
import sqlite3

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

PORT_OPTIONS = [f"PT-{i}" for i in range(1, 9)] + [f"LC-{i}" for i in range(1, 9)]

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


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS equations (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            expression TEXT NOT NULL
        )
        """)
    
    conn.commit()
    conn.close()

def get_equations_from_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT id, name, expression FROM equations")
    rows = cursor.fetchall()

    conn.close()

    return [
        {
            "id": row[0],
            "name": row[1],
            "expression": row[2]
        }
        for row in rows
    ]
init_db()

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
def api_config():
    return {
        "ports": PORT_OPTIONS,
        "equations": get_equations_from_db(),
        "sensors": list(sensors.values()),
        "graphs": list(graphs.values()),
        "read_rate_hz": "--",
        "active_graphs": len(graphs),
    }


@app.post("/api/equations")
def add_equation(payload: EquationPayload):
    eq_id = str(uuid4())
    equation = {
        "id": eq_id,
        "name": payload.name,
        "expression": payload.expression,
    }
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO equations (id, name, expression)
        VALUES (?, ?, ?)
        """,
        (eq_id, payload.name, payload.expression),)
    conn.commit()
    conn.close()
    #sqlite.save this equation
    return equation



@app.patch("/api/equations/{equation_id}")
def edit_equation(equation_id: str, payload: EquationPayload):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE equations
        SET name = ?, expression = ?
        WHERE id = ?
        """,
        (payload.name, payload.expression, equation_id),
    )

    conn.commit()

    if cursor.rowcount == 0:
        conn.close()
        return {"error": "Equation not found"}

    conn.close()

    return {
        "id": equation_id,
        "name": payload.name,
        "expression": payload.expression,
    }




@app.post("/api/sensors")
def add_sensor(payload: SensorPayload):
    sensor_id = str(uuid4())
    sensor = {
        "id": sensor_id,
        "name": payload.name,
        "port": payload.port,
        "equation_id": payload.equation_id,
    }
    sensors[sensor_id] = sensor
    return sensor


@app.patch("/api/sensors/{sensor_id}")
def edit_sensor(sensor_id: str, payload: SensorPayload):
    if sensor_id not in sensors:
        return {"error": "Sensor not found"}

    sensors[sensor_id]["name"] = payload.name
    sensors[sensor_id]["port"] = payload.port
    sensors[sensor_id]["equation_id"] = payload.equation_id
    return sensors[sensor_id]


@app.post("/api/graphs")
def add_graph(payload: GraphPayload):
    graph_id = str(uuid4())
    graph = {
        "id": graph_id,
        "name": payload.name,
        "sensor_id": payload.sensor_id,
    }
    graphs[graph_id] = graph
    return graph


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

            if action == "subscribe":
                manager.subscribe(websocket, *arguments)
            elif action == "unsubscribe":
                manager.unsubscribe(websocket, *arguments)

    except WebSocketDisconnect:
        manager.disconnect(websocket)