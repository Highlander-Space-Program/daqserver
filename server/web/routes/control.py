from server.streaming import stream
from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from server.web.resources import templates

router = APIRouter(tags=["controls"])


@router.get("/controls", response_class=HTMLResponse)
async def controls_page(request: Request):
    return templates.TemplateResponse("controls.html", {"request": request})

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