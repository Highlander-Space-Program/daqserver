import aiosqlite
from dataclasses import dataclass
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse

from server.pool import Datapool, Topic
from server.states import DB_PATH
from server.web.resources import get_datapool, templates
from server.streaming.switches import (
    GLOBAL_SWITCH_STATES,
    Start,
    Stop,
    Timeout,
    SwitchID,
)


router = APIRouter(prefix="/switch", tags=["switch"])


@dataclass
class CommandPayload:
    action: str
    switch_number: int | None = None
    duration: int | None = None  # in milliseconds


@dataclass
class ScriptPayload:
    name: str
    workspace_json: str


# Database initialization
async def init_db(db):
    await db.execute(
        "CREATE TABLE IF NOT EXISTS scripts (id INTEGER PRIMARY KEY, name TEXT, workspace TEXT)"
    )


@router.post("/api/execute")
async def execute_sequence(
    commands: list[CommandPayload], datapool: Datapool = Depends(get_datapool)
):
    """Receives parsed Blockly blocks and publishes them to the executor pool."""
    valid_commands = []
    for cmd in commands:
        command = None
        if cmd.action == "start":
            if cmd.switch_number is None:
                return {"status": "error"}
            command = Start(SwitchID(cmd.switch_number, 1))
        elif cmd.action == "stop":
            if cmd.switch_number is None:
                return {"status": "error"}
            command = Stop(SwitchID(cmd.switch_number, 1))
        elif cmd.action == "wait":
            # Convert milliseconds to seconds for the Timeout command
            if cmd.duration is None:
                return {"status": "error"}
            command = Timeout(cmd.duration / 1000.0)
        valid_commands.append(command)

    datapool.publish(Topic.SWITCHCOM, valid_commands)
    return {"status": "Sequence queued"}


@router.get("/api/state")
async def get_states():
    """Frontend polls this to get the real-time switch states."""
    return GLOBAL_SWITCH_STATES


@router.post("/api/script")
async def save_script(payload: ScriptPayload):
    """Saves the raw Blockly workspace JSON to sqlite."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO scripts (name, workspace) VALUES (?, ?)",
            (payload.name, payload.workspace_json),
        )
        await db.commit()
    return {"status": "Saved"}


@router.get("/api/scripts")
async def list_scripts():
    """Returns a list of all saved scripts to populate the frontend dropdown."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute("SELECT id, name FROM scripts")
        rows = await cursor.fetchall()
        return [{"id": row["id"], "name": row["name"]} for row in rows]


@router.get("/api/script/{script_id}")
async def get_script(script_id: int):
    """Fetches the specific workspace JSON for a given script ID."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cursor = await db.execute(
            "SELECT workspace FROM scripts WHERE id = ?", (script_id,)
        )
        row = await cursor.fetchone()
        if row:
            return {"workspace_json": row["workspace"]}
        return {"error": "Script not found"}


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("switch.html", {"request": request})
