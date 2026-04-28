import aiosqlite
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from server.pool import Datapool, Topic
from server.states import DB_PATH
from server.web.resources import pass_to_frontend
from server.web.routes import dashboard, control, camera

app = FastAPI()
app.mount("/static", StaticFiles(directory="./server/web/static"), name="static")
app.include_router(dashboard.router)
app.include_router(control.router)
app.include_router(camera.router)


async def init_db(datapool: Datapool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS equations (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                expression TEXT NOT NULL
            )
        """)

        await db.execute("""
            CREATE TABLE IF NOT EXISTS sensors (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                port TEXT NOT NULL,
                equation_id TEXT
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS graphs (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                sensor_id TEXT NOT NULL
            )
        """)

        await db.commit()

    datapool.subscribe(Topic.SENSORDATA, pass_to_frontend)
