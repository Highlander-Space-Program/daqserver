from fastapi import APIRouter, Request
from starlette.responses import HTMLResponse

from server.web.resources import templates

router = APIRouter(
    prefix="/camera",
    tags=["camera"],
)


@router.get("/", response_class=HTMLResponse)
async def cameras_page(request: Request):
    return templates.TemplateResponse("cameras.html", {"request": request})
