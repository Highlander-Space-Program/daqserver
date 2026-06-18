from server.streaming import stream
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import HTMLResponse
from pydantic import BaseModel
from datetime import datetime

from server.web.resources import templates


class ControlCommand(BaseModel):
    command: int

ARM_COMMANDS = {
    "Igniter": 0x00,
    "Auto Ignition": 0x02,
    "Servos": 0x04,
    "Servo_1": 0x06,
    "Servo_2": 0x08,
    "Servo_3": 0x0A,
    "Igniter_Actual": 0x0C, #not system flag
    "LED": 0x0F
}

ABORT_COMMANDS = {
    "Igniter": 0x01,
    "Auto Ignition": 0x03,
    "Servos": 0x05,
    "Servo_1": 0x07,
    "Servo_2": 0x09,
    "Servo_3": 0x0B,
    "Igniter_Actual": 0x0D, #not system flag
    "LED": 0x0E
}


router = APIRouter(prefix="/controls", tags=["controls"])


# @router.get("/", response_class=HTMLResponse)
# async def controls_page(request: Request):
#     return templates.TemplateResponse("controls2.html", {"request": request})


@router.get("/api/breakwire")
async def get_breakwire_status(request: Request):
    return request.app.state.control_publisher.get_breakwire_status()


@router.post("/api/command")
async def send_control_command(request: Request, payload: ControlCommand):
    sent = request.app.state.control_publisher.send_command(payload.command)
    if not sent:
        raise HTTPException(
            status_code=503,
            detail="MQTT control publisher is not connected",
        )

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
        "port": "/dev/mockUSB0",
        "status": "Connected"
    },
    "boards": {
        "Igniter Board": False,
        "Servo Board": False,
    },
    "important_status": {
        # "System": True,
        "Igniter": True,
        "Servos": True,
        "Auto Ignition": True,
    },
    "servos": [
        {"name": "Servo 1", "status": "CLOSED"},
        {"name": "Servo 2", "status": "CLOSED"},
        {"name": "Servo 3", "status": "CLOSED"},
    ],
    "igniter": {
        "status": "OFF"
    },
    "breakwire": {
        "connected": False
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


@router.get("/api/status")
async def get_status():
    return state


@router.post("/api/connect")
async def connect_xbee():
    state["xbee"]["connected"] = True
    state["xbee"]["status"] = "Connected"
    state["xbee"]["port"] = "/dev/mockUSB0"

    state["boards"]["Igniter Board"] = True
    state["boards"]["Servo Board"] = True

    log_event("Mock autodetect start")
    log_event("MQTT connected on /dev/mockUSB0")
    return {"ok": True}


@router.post("/api/disconnect")
async def disconnect_xbee():
    state["xbee"]["connected"] = False
    state["xbee"]["status"] = "Disconnected"
    state["xbee"]["port"] = ""

    state["boards"]["Igniter Board"] = False
    state["boards"]["Servo Board"] = False

    log_event("Mock disconnect start")
    log_event("User mock disconnect")
    return {"ok": True}


@router.post("/api/arm")
async def arm_status(request: Request, action: StatusAction):
    if action.name not in state["important_status"]:
        raise HTTPException(status_code=400, detail="Unknown status name")

    command = ARM_COMMANDS.get(action.name)
    if command is not None:
        await send_control_command(request, ControlCommand(command=command))

    state["important_status"][action.name] = True
    log_event(f"{action.name} ARMED")

    return {"ok": True}


@router.post("/api/abort")
async def abort_status(request: Request, action: StatusAction):
    if action.name not in state["important_status"]:
        raise HTTPException(status_code=400, detail="Unknown status name")

    command = ABORT_COMMANDS.get(action.name)
    if command is not None:
        await send_control_command(request, ControlCommand(command=command))

    state["important_status"][action.name] = False
    log_event(f"{action.name} ABORTED")

    return {"ok": True}


@router.post("/api/servo/open")
async def open_servo(action: ServoAction):
    row = action.row
    if 0 <= row < 3:
        state["servos"][row]["status"] = "OPEN"
        log_event(f"Servo {row + 1} OPEN")
    return {"ok": True}


@router.post("/api/servo/close")
async def close_servo(action: ServoAction):
    row = action.row
    if 0 <= row < 3:
        state["servos"][row]["status"] = "CLOSED"
        log_event(f"Servo {row + 1} CLOSED")
    return {"ok": True}


@router.post("/api/igniter/fire")
async def fire_igniter():
    state["igniter"]["status"] = "ON"
    log_event("Igniter FIRED")
    return {"ok": True}


@router.post("/api/igniter/shutoff")
async def shutoff_igniter():
    state["igniter"]["status"] = "OFF"
    log_event("Igniter SHUT OFF")
    return {"ok": True}


@router.post("/api/ping")
async def ping_board():
    log_event("Ping sent to board")
    return {"ok": True, "message": "Ping sent"}


@router.post("/api/breakwire/toggle")
async def toggle_breakwire():
    state["breakwire"]["connected"] = not state["breakwire"]["connected"]
    status = "CONNECTED" if state["breakwire"]["connected"] else "DISCONNECTED"
    log_event(f"Breakwire {status}")
    return {"ok": True}
