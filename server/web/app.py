"""
This module defines `app` and database for the frontend

The database for the frontend is going to save the charts and equations
"""

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

app = FastAPI()
app.mount("/static", StaticFiles(directory="./server/web/static"), name="static")
templates = Jinja2Templates(directory="./server/web/templates")


# Serve the main dashboard page
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})
