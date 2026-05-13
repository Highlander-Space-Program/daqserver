from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from server.web.resources import templates
from pydantic import BaseModel

class ControlCommand(BaseModel):
    command: int

router = APIRouter(prefix="/controls", tags=["controls"])


@router.get("/", response_class=HTMLResponse)
async def controls_page(request: Request):
    return templates.TemplateResponse("controls.html", {"request": request})

@router.post("/api/command")
async def send_control_command(request: Request, payload: ControlCommand):
    request.app.state.control_publisher.send_command(payload.command)
    return {"success": True}
