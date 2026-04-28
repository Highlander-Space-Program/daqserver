import asyncio

import uvicorn
from dotenv import load_dotenv

from server.db.influx import init_influx
from server.pool import Datapool
from server.streaming.stream import init_streaming
from server.web.app import app, init_db
from server.logger import server_logger as logger


async def start():
    datapool = Datapool(asyncio.get_running_loop())

    await init_db(datapool)
    init_influx(datapool)
    init_streaming(datapool)

    logger.info("Listening on http://localhost:8000")
    config = uvicorn.Config(app, host="0.0.0.0", port=8000)
    server = uvicorn.Server(config)
    await server.serve()


def main():
    load_dotenv()

    try:
        asyncio.run(start())
    except KeyboardInterrupt:
        pass
    finally:
        logger.info("Shutting down server")


if __name__ == "__main__":
    main()

# vim: et:sw=4
