import os
import asyncio

from server.db.bridge import Bridge
from server.db.pool_bridge import PoolBridge
from server.logger import db_logger as logger
from server.pool import Datapool


bridge = None
pool_bridge = None


def init_influx(datapool: Datapool):
    global bridge, pool_bridge
    influx_url = os.getenv("INFLUXDB_URL")
    influx_token = os.getenv("INFLUXDB_TOKEN")
    influx_database = os.getenv("INFLUXDB_DATABASE")
    mqtt_host = os.getenv("MQTT_HOST")
    mqtt_port = int(os.getenv("MQTT_PORT", 1883))
    influx_exists = all([influx_url, influx_token, influx_database, mqtt_host])

    if influx_exists:
        #logger.info("Found environment variables for Influx. Start...")
        #bridge = Bridge(
        #    influx_url, influx_token, influx_database, mqtt_host, mqtt_port
        #)
        #bridge.start()

        pool_bridge = PoolBridge(
            datapool, influx_url, influx_token, influx_database
        )
        asyncio.create_task(pool_bridge.start())
    else:
        logger.warn(
            "Influx is not starting due to missing some environment variables"
        )


async def shutdown_influx():
    if bridge is not None:
        bridge.shutdown()

    if pool_bridge is not None:
        await pool_bridge.shutdown()
