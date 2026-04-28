from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from server.web.resources import templates

router = APIRouter(prefix="/controls", tags=["controls"])


@router.get("/controls", response_class=HTMLResponse)
async def controls_page(request: Request):
    return templates.TemplateResponse("controls.html", {"request": request})
