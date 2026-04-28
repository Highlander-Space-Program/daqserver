import os

from server.db.bridge import Bridge
from server.logger import db_logger as logger
from server.pool import Datapool


def init_influx(datapool: Datapool):
    influx_url = os.getenv("INFLUXDB_URL")
    influx_token = os.getenv("INFLUXDB_TOKEN")
    influx_database = os.getenv("INFLUXDB_DATABASE")
    mqtt_host = os.getenv("MQTT_HOST")
    mqtt_port = int(os.getenv("MQTT_PORT", 1883))
    influx_exists = all([influx_url, influx_token, influx_database, mqtt_host])
    if influx_exists:
        logger.info("Found environment variables for Influx. Start...")
        bridge = Bridge(
            influx_url, influx_token, influx_database, mqtt_host, mqtt_port
        )
        bridge.start()
    else:
        logger.warn(
            "Influx is not starting due to missing some environment variables"
        )
