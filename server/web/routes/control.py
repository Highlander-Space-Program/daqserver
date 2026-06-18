from server.streaming import stream
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel
from starlette.responses import HTMLResponse
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import random
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
        "port": "dev/mockUSB0",
        "status": "Connected"
    },
    "boards": {
        "Igniter Board": False,
        "Sensor Board": False,
        "Solenoid Board": False
    },
    "important_status": {
        # "System": True,
        "Igniter": True,
        "Servos": True,
        "Auto Ignition": True,
    },
    "solenoids": [],
    "event_log": [],
    "sensors": {
        "tc": [0.0] * 12,
        "lc": [0.0] * 12,
        "pt": [0.0] * 12,
    }
}
def log_event(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    state["event_log"].append(f"[{timestamp}] {message}")
    state["event_log"] = state["event_log"][-50:] #can change this number to increase/decrease log size

# Initialize solenoid table 
# helps to see data rn at range 12
for i in range(12):
    state["solenoids"].append({
        "valve": i + 1,
        "status": "CLOSED",
        "power": "DISCONNECTED" 
    })

#classes (table of contents)
from pydantic import BaseModel

class StatusAction(BaseModel):
    name: str

class SolenoidAction(BaseModel):
    row: int

#testing data --> not real just for testing purposes
def update_mock_data():
    state["boards"]["Igniter Board"] = random.choice([True, False])
    state["boards"]["Sensor Board"] = True
    state["boards"]["Solenoid Board"] = random.choice([True, False])

    state["sensors"]["tc"] = [round(random.uniform(60, 250), 1) for _ in range(12)]
    state["sensors"]["lc"] = [round(random.uniform(0, 500), 1) for _ in range(12)]
    state["sensors"]["pt"] = [round(random.uniform(0, 300), 1) for _ in range(12)]

#routes; path operations, help the core components that link specific url path and 
#http method tp a python function, can also request the classes 
# will update this code later after I ask for more specific info 
#mock data 
#have this commented for now
#@app.get("/", response_class=HTMLResponse)
#async def home(request: Request):
#    return templates.TemplateResponse(
#        request=request,
#        name="index.html",
#       context={}
#    )


#@app.get("/api/status")
#async def get_status():
#    return JSONResponse(state)

#new get api status 
@router.get("/api/status")
async def get_status():
    return state



@router.post("/api/connect")
async def connect_xbee():
    state["xbee"]["connected"] = True
    state["xbee"]["status"] = "Connected"
    state["xbee"]["port"] = "/dev/mockUSB0"

    state["boards"]["Igniter Board"] = True
    state["boards"]["Sensor Board"] = True
    state["boards"]["Solenoid Board"] = True
    log_event("Mock Autodetect Start")
    log_event("XBee connected on /dev/mockUSB0")
    return {"ok": True}


@router.post("/api/disconnect")
async def disconnect_xbee():
    state["xbee"]["connected"] = False
    state["xbee"]["status"] = "Disconnected"
    state["xbee"]["port"] = ""
    log_event("Mock Disconnect Start")
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


@router.post("/api/solenoid/open")
async def open_solenoid(action: SolenoidAction):
    row = action.row
    if 0 <= row < 12:
        state["solenoids"][row]["status"] = "OPEN"
        log_event(f"Solenoid {row + 1} actuated OPEN")
    return {"ok": True}


@router.post("/api/solenoid/close")
async def close_solenoid(action: SolenoidAction):
    row = action.row
    if 0 <= row < 12:
        state["solenoids"][row]["status"] = "CLOSED"
        log_event(f"Solenoid {row + 1} actuated CLOSED")
    return {"ok": True}


@router.post("/api/solenoid/power")
async def toggle_power(action: SolenoidAction):
    row = action.row
    if 0 <= row < 12:
        current = state["solenoids"][row]["power"]
        if current == "CONNECTED":
            state["solenoids"][row]["power"] = "DISCONNECTED"
            log_event(f"Solenoid {row + 1} power DISCONNECTED")
        else:
            state["solenoids"][row]["power"] = "CONNECTED"
            log_event(f"Solenoid {row + 1} power CONNECTED")
    return {"ok": True}
