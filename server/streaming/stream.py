from threading import Thread

from labjack.ljm import LJMError
from server.pool import Datapool
from server.streaming.lj import LabJackTest, LabjackT7
from server.streaming.sensors import load_sensors_from_json
from server.logger import streaming_logger as logger


def init_streaming(datapool: Datapool):
    t7 = LabjackT7(datapool)
    try:
        t7.open("Ethernet")
        sensors = load_sensors_from_json("labjack_channels.json", board="T7")
        thread = Thread(target=t7.stream, args=(sensors,), daemon=True)
        thread.start()
    except AttributeError:
        logger.warn(
            "Unable to open labjack due to not having the right libraries and drivers"
        )
    except LJMError:
        logger.warn("Unable to open t7 labjack through ethernet")

    lj_test = LabJackTest(datapool)
    lj_test.init()
