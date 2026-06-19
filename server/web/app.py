from contextlib import asynccontextmanager
import aiosqlite
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from server.pool import Datapool, Topic
from server.states import DB_PATH
from server.web.resources import pass_to_frontend
from server.web.routes import dashboard, control, camera, switch

from server.mqtt import ControlPublisher


def init_app(datapool: Datapool):
    datapool.subscribe(Topic.SENSORDATA, pass_to_frontend)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.datapool = datapool
        app.state.control_publisher = ControlPublisher()

        yield

        app.state.control_publisher.shutdown()
        # cleanup if needed

    app = FastAPI(lifespan=lifespan)
    app.mount(
        "/static", StaticFiles(directory="./server/web/static"), name="static"
    )
    app.include_router(dashboard.router)
    app.include_router(control.router)
    app.include_router(camera.router)
    app.include_router(switch.router)

    return app


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await dashboard.init_db(db)
        await switch.init_db(db)
        await db.commit()
