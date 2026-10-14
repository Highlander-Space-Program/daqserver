
import asyncio
import os

from server.logger import db_logger as logger
from server.pool import Datapool
from server.streaming.grafana_live import GrafanaLivePublisher

grafana_live = None
grafana_live_task = None


def init_grafana_live(datapool: Datapool):
    global grafana_live, grafana_live_task

    grafana_url = os.getenv("GRAFANA_URL")
    grafana_token = os.getenv("GRAFANA_TOKEN")
    grafana_stream_id = os.getenv("GRAFANA_STREAM_ID", "daq")

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

    grafana_live_task = asyncio.create_task(grafana_live.start())


async def shutdown_grafana_live():
    global grafana_live, grafana_live_task

    if grafana_live is not None:
        await grafana_live.shutdown()

    if grafana_live_task is not None:
        try:
            await grafana_live_task
        except asyncio.CancelledError:
            pass
        finally:
            grafana_live_task = None

    grafana_live = None

