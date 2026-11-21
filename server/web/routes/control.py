import asyncio
import json
from pathlib import Path
from server.streaming import stream
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import HTMLResponse
from datetime import datetime

from server.logger import server_logger as logger
from server.mqtt import (
    DEFAULT_COMMAND_TIMEOUT_SECONDS,
    CommandError,
    CommandRejected,
    CommandTimeout,
    PublisherUnavailable,
)
from server.web.resources import templates


class ControlCommand(BaseModel):
    command: int


# Command codes, servo/board names, etc. live in controls_config.json at the
# repo root so they can be changed without touching code.
CONTROLS_CONFIG_PATH = Path(__file__).resolve().parents[3] / "controls_config.json"


def load_controls_config(path: Path = CONTROLS_CONFIG_PATH) -> dict:
    with open(path, "r") as f:
        return json.load(f)


config = load_controls_config()

# Command codes are written as hex strings ("0x06") in the JSON file
ARM_COMMANDS = {
    name: int(codes["arm"], 0) for name, codes in config["commands"].items()
}
ABORT_COMMANDS = {
    name: int(codes["abort"], 0) for name, codes in config["commands"].items()
}

LED_BLINK_COUNT = config["ping"]["led_blink_count"]
LED_BLINK_DELAY_SECONDS = config["ping"]["led_blink_delay_seconds"]
MOCK_XBEE_PORT = config["mock_xbee_port"]
COMMAND_TIMEOUT_SECONDS = config.get(
    "command_response_timeout_seconds", DEFAULT_COMMAND_TIMEOUT_SECONDS
)

COMMAND_ERROR_STATUS_CODES: dict[type[CommandError], int] = {
    PublisherUnavailable: 503,
    CommandTimeout: 504,
    CommandRejected: 502,
}


router = APIRouter(prefix="/controls", tags=["controls"])


# @router.get("/", response_class=HTMLResponse)
# async def controls_page(request: Request):
#     return templates.TemplateResponse("controls2.html", {"request": request})


@router.get("/api/breakwire")
async def get_breakwire_status(request: Request):
    return request.app.state.control_publisher.get_breakwire_status()


async def run_command(request: Request, command: int) -> dict:
    """Send a command and wait for the board's ack.

    On failure, logs the error (server log + UI event log) and raises an
    HTTPException so callers never update state for a command that failed.
    """
    publisher = request.app.state.control_publisher
    try:
        return await publisher.send_command(
            command, timeout=COMMAND_TIMEOUT_SECONDS
        )
    except CommandError as exc:
        if not isinstance(exc, PublisherUnavailable):
            label = f"Command 0x{command:02X} (id {exc.command_id})"
            logger.error("%s failed: %s", label, exc.message)
            log_event(f"{label} failed: {exc.message}")
        raise HTTPException(
            status_code=COMMAND_ERROR_STATUS_CODES.get(type(exc), 500),
            detail=exc.message,
        ) from exc


@router.post("/api/command")
async def send_control_command(request: Request, payload: ControlCommand):
    await run_command(request, payload.command)
    return {"success": True}


@router.post("/api/sensors/{sensor_id}/tare")
async def tare_sensor(sensor_id: str):
    print(f"Tare requested for sensor: {sensor_id}")

    if stream.labjack_instance is None:
        return {
            "status": "error",
            "message": "LabJack not initialized"
        }
    stream.labjack_instance.tare({}, "")

    return {
        "status": "ok",
        "sensor_id": sensor_id
    }




@router.get("/", response_class=HTMLResponse)
async def get_page(request: Request):
    return templates.TemplateResponse(
        #request=request,
        #name="frontendview.html",
        "controls.html",
        #context={}
        {"request": request}
    )


state = {
    "xbee": {
        "connected": True,
        "port": MOCK_XBEE_PORT,
        "status": "Connected"
    },
    "boards": {name: False for name in config["boards"]},
    "important_status": dict(config["system_flags"]),
    "servos": [
        {"name": name, "status": "CLOSED"} for name in config["servos"]
    ],
    "igniter": {
        "status": "OFF"
    },
    "event_log": []
}


def log_event(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    state["event_log"].append(f"[{timestamp}] {message}")
    state["event_log"] = state["event_log"][-50:]


class StatusAction(BaseModel):
    name: str


class ServoAction(BaseModel):
    row: int


def get_servo(row: int):
    if not 0 <= row < len(state["servos"]):
        raise HTTPException(status_code=400, detail="Invalid servo row")

    return state["servos"][row]


@router.get("/api/status")
async def get_status(request: Request):
    breakwire_status = (
        request.app.state.control_publisher.get_breakwire_status()["status"]
    )
    return {
        **state,
        "breakwire": {
            "status": breakwire_status,
            "connected": breakwire_status == "connected",
        },
    }


@router.post("/api/connect")
async def connect_xbee():
    state["xbee"]["connected"] = True
    state["xbee"]["status"] = "Connected"
    state["xbee"]["port"] = MOCK_XBEE_PORT

    for board in state["boards"]:
        state["boards"][board] = True

    log_event("Mock autodetect start")
    log_event(f"MQTT connected on {MOCK_XBEE_PORT}")
    return {"ok": True}


@router.post("/api/disconnect")
async def disconnect_xbee():
    state["xbee"]["connected"] = False
    state["xbee"]["status"] = "Disconnected"
    state["xbee"]["port"] = ""

    for board in state["boards"]:
        state["boards"][board] = False

    log_event("Mock disconnect start")
    log_event("User mock disconnect")
    return {"ok": True}


@router.post("/api/arm")
async def arm_status(request: Request, action: StatusAction):
    if action.name not in state["important_status"]:
        raise HTTPException(status_code=400, detail="Unknown status name")

    command = ARM_COMMANDS.get(action.name)
    if command is not None:
        await run_command(request, command)

    state["important_status"][action.name] = True
    log_event(f"{action.name} ARMED")

    return {"ok": True}


@router.post("/api/abort")
async def abort_status(request: Request, action: StatusAction):
    if action.name not in state["important_status"]:
        raise HTTPException(status_code=400, detail="Unknown status name")

    command = ABORT_COMMANDS.get(action.name)
    if command is not None:
        await run_command(request, command)

    state["important_status"][action.name] = False
    log_event(f"{action.name} ABORTED")

    return {"ok": True}


@router.post("/api/servo/open")
async def open_servo(request: Request, action: ServoAction):
    servo = get_servo(action.row)
    if servo["status"] == "OPEN":
        return {"ok": True}

    command = ARM_COMMANDS[servo["name"]]
    await run_command(request, command)

    servo["status"] = "OPEN"
    log_event(f"Servo {action.row + 1} OPEN")
    return {"ok": True}


@router.post("/api/servo/close")
async def close_servo(request: Request, action: ServoAction):
    servo = get_servo(action.row)
    if servo["status"] == "CLOSED":
        return {"ok": True}

    command = ABORT_COMMANDS[servo["name"]]
    await run_command(request, command)

    servo["status"] = "CLOSED"
    log_event(f"Servo {action.row + 1} CLOSED")
    return {"ok": True}


@router.post("/api/igniter/fire")
async def fire_igniter(request: Request):

    if state["igniter"]["status"] != "ON":
        command = ARM_COMMANDS["Igniter_Actual"]
        await run_command(request, command)

    state["igniter"]["status"] = "ON"
    log_event("Igniter FIRED")
    return {"ok": True}


@router.post("/api/igniter/shutoff")
async def shutoff_igniter(request: Request):

    if state["igniter"]["status"] != "OFF":
        command = ABORT_COMMANDS["Igniter_Actual"]
        await run_command(request, command)

    state["igniter"]["status"] = "OFF"
    log_event("Igniter SHUT OFF")
    return {"ok": True}


@router.post("/api/ping")
async def ping_board(request: Request):
    for _ in range(LED_BLINK_COUNT):
        await run_command(request, ARM_COMMANDS["LED"])
        await asyncio.sleep(LED_BLINK_DELAY_SECONDS)
        await run_command(request, ABORT_COMMANDS["LED"])
        await asyncio.sleep(LED_BLINK_DELAY_SECONDS)

    log_event("Ping blink sent to board")
    return {"ok": True, "message": "Ping sent"}

