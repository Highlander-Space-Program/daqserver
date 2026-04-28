from dataclasses import dataclass
from typing import Any
from uuid import uuid4
import aiosqlite
from aiosqlite import Connection
from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from starlette.responses import HTMLResponse
from server.states import DB_PATH, PORT_OPTIONS
from server.web.resources import manager, templates
from server.web.connection import ErrorMessage

sensors: dict[str, dict[str, Any]] = {}
graphs: dict[str, dict[str, Any]] = {}

router = APIRouter(tags=["dashboard"])


@dataclass
class EquationPayload:
    name: str
    expression: str


@dataclass
class SensorPayload:
    name: str
    port: str
    equation_id: str | None = None


@dataclass
class GraphPayload:
    name: str
    sensor_id: str


async def get_db():
    async with aiosqlite.connect(DB_PATH) as db:
        yield db


async def get_equations_from_db(db: Connection):
    async with db.execute("SELECT id, name, expression FROM equations") as cursor:
        rows = await cursor.fetchall()

    return [{"id": row[0], "name": row[1], "expression": row[2]} for row in rows]


async def get_sensors_from_db(db: Connection):
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


async def get_graphs_from_db(db: Connection):
    async with db.execute("SELECT id, name, sensor_id FROM graphs") as cursor:
        rows = await cursor.fetchall()
    return [{"id": row[0], "name": row[1], "sensor_id": row[2]} for row in rows]


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@router.get("/api/config")
async def api_config(db: aiosqlite.Connection = Depends(get_db)):
    graphs_list = await get_graphs_from_db(db)
    return {
        "ports": list(PORT_OPTIONS.keys()),
        "equations": await get_equations_from_db(db),
        "sensors": await get_sensors_from_db(db),
        "graphs": graphs_list,
        "read_rate_hz": "--",
        "active_graphs": len(graphs_list),
    }


@router.post("/api/equations")
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


@router.patch("/api/equations/{equation_id}")
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


@router.post("/api/sensors")
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


@router.patch("/api/sensors/{sensor_id}")
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


@router.post("/api/graphs")
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


@router.get("/api/latest")
def api_latest():
    return {
        "read_rate_hz": "--",
        "active_graphs": len(graphs),
        "values": {},
    }


@router.websocket("/ws")
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
                for sensor in arguments:
                    manager.subscribe(websocket, sensor)
            elif action == "unsubscribe":
                manager.unsubscribe(websocket, *arguments)

    except WebSocketDisconnect:
        manager.disconnect(websocket)


@router.delete("/api/equations/{equation_id}")
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


@router.delete("/api/sensors/{sensor_id}")
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
