import os
import asyncio

from server.logger import db_logger as logger
from server.pool import Datapool
from server.streaming.grafana_live import GrafanaLivePublisher


grafana_live = None


def init_grafana_live(datapool: Datapool):

    global grafana_live

    grafana_url = os.getenv("GRAFANA_URL")
    grafana_token = os.getenv("GRAFANA_TOKEN")
    grafana_stream_id = os.getenv(
        "GRAFANA_STREAM_ID",
        "daq",
    )

    if not grafana_url or not grafana_token:
        logger.warning(
            "Grafana Live is not starting: "
            "missing GRAFANA_URL or GRAFANA_TOKEN"
        )
        return

    grafana_live = GrafanaLivePublisher(
        datapool=datapool,
        url=grafana_url,
        token=grafana_token,
        stream_id=grafana_stream_id,
    )

    asyncio.create_task(
        grafana_live.start()
    )


async def shutdown_grafana_live():

    if grafana_live is not None:
        await grafana_live.shutdown()
