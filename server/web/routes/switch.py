import aiosqlite
from dataclasses import dataclass
from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from server.states import DB_PATH
from server.web.resources import templates
from server.streaming import stream as streaming
from server.streaming.switches import (
    GLOBAL_SWITCH_STATES,
    SWITCH_OPTIONS,
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
    """Execute a sequence of Blockly commands on the active LabJack."""
    executor = streaming.command_executor
    if executor is None:
        raise HTTPException(
            status_code=503,
            detail="LabJack is not initialized.",
        )
    valid_commands = []
    for cmd in commands:
        if cmd.action in ("start", "stop"):
            if cmd.switch_number is None:
                raise HTTPException(
                    status_code=400,
                    detail="A switch number is required.",
                )
            switch_key = f"S{cmd.switch_number}"
            if switch_key not in SWITCH_OPTIONS:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid switch number: {cmd.switch_number}",
                )
            switch_id = SwitchID(cmd.switch_number, 1)
            if cmd.action == "start":
                valid_commands.append(Start(switch_id))
            else:
                valid_commands.append(Stop(switch_id))
        elif cmd.action == "wait":
            if cmd.duration is None or cmd.duration < 0:
                raise HTTPException(
                    status_code=400,
                    detail="A non-negative duration is required.",
                )
            # Convert milliseconds to seconds.
            valid_commands.append(Timeout(cmd.duration / 1000.0))
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Unknown command: {cmd.action}",
            )
    await executor.listen_for_commands(valid_commands)
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
