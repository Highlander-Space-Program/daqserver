"""
This module defines `app` and database for the frontend

The database for the frontend is going to save the charts and equations
"""

from typing import Any
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.responses import HTMLResponse

from server.web.connection import ConnectionManager, ErrorMessage

app = FastAPI()
manager = ConnectionManager()
app.mount("/static", StaticFiles(directory="./server/web/static"), name="static")
templates = Jinja2Templates(directory="./server/web/templates")


# Serve the main dashboard page
@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)

    try:
        while True:
            msg: dict[str, Any] = await websocket.receive_json()

            action: str | None = msg.get("action")
            arguments: list[str] | None = msg.get("arguments")

            if action is None or arguments is None:
                await websocket.send_json(
                    ErrorMessage(
                        "You need to specify which action you want to perform and the arguments for that action"
                    ).to_dict()
                )
                return

            # TODO: argument counts need to be checked
            if action == "subscribe":
                manager.subscribe(websocket, *arguments)

            elif action == "unsubscribe":
                manager.unsubscribe(websocket, *arguments)

    except WebSocketDisconnect:
        manager.disconnect(websocket)