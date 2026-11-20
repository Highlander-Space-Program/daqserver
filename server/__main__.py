import asyncio
import os

import uvicorn
from dotenv import load_dotenv

from server.logger import server_logger as logger
from server.streaming.grafana_live import GrafanaLivePublisher
from server.streaming.influx_writer import InfluxPublisher
from server.streaming.stream import init_streaming
from server.streaming import stream as streaming
from server.web.app import init_app, init_db
from server.grafana_setup import setup_grafana_dashboard
from labjack.ljm import LJMError

async def start(grafana, influx):
    t7 = None
    worker = None
   
    try:
        loop = asyncio.get_running_loop()

        if grafana is not None:
            await grafana.connect()

        await init_db()
#        setup_grafana_dashboard()
        app = init_app()

        t7, worker = init_streaming(
            loop = loop,
            grafana_publisher=grafana,
            influx_publisher=influx,
        )

        logger.info("Listening on http://localhost:8000")

        config = uvicorn.Config(app, host="0.0.0.0", port=8000)
        server = uvicorn.Server(config)
        await server.serve()
    except AttributeError:
        logger.warning(
            "Unable to open labjack due to not having the right libraries and drivers"
        )
    except LJMError:
        logger.warning("Unable to open t7 labjack through ethernet")

    finally:
        logger.info("[Shutdown] cleaning up...")
        if t7 is not None:
            t7.stop()
        if worker is not None:
            worker.join(timeout=5)
            if worker.is_alive():
                logger.critical(
                    "LabJack acquisition thread did not stop. "
                    "Labjack handle will remain open."
                )
            else:
                if t7 is not None:
                    t7.close()
        elif t7 is not None:
            t7.close()
        if grafana is not None:
            await grafana.close()

def main():
    load_dotenv()

    grafana = None
    influx = None


    try:
        # Initialize Grafana Live publisher.
        if os.getenv("GRAFANA_TOKEN"):
            grafana = GrafanaLivePublisher()
        else:
            logger.warning(
                "GRAFANA_TOKEN not set. Grafana Live publishing disabled."
            )

        # Initialize InfluxDB publisher.
        influx_url = os.getenv("INFLUXDB_URL")
        influx_token = os.getenv("INFLUXDB_TOKEN")
        influx_database = os.getenv("INFLUXDB_DATABASE")

        if all([influx_url, influx_token, influx_database]):
            influx = InfluxPublisher(
                host=influx_url,
                token=influx_token,
                database=influx_database,
            )
        else:
            logger.warning(
                "InfluxDB configuration incomplete. "
                "InfluxDB publishing disabled."
            )

        asyncio.run(start(grafana, influx))

    except KeyboardInterrupt:
        logger.info("Shutting down server.")

    except Exception:
        logger.exception("Application failed.")
        raise

    finally:
        if influx is not None:
            influx.close()


if __name__ == "__main__":
    main()

# vim: et:sw=4
