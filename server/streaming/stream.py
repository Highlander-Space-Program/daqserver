from threading import Thread
from server.web.resources import manager
from labjack.ljm import LJMError
from server.streaming.lj import LabJackTest, LabjackT7
from server.streaming.sensors import load_sensors_from_json
from server.logger import streaming_logger as logger
from server.streaming.switches import CommandExecutor

labjack_instance = None
command_executor = None


def init_streaming(loop):
    global labjack_instance
    labjack_instance = LabjackT7(manager, loop)

    t7 = labjack_instance
    try:
        t7.open("Ethernet", "10.10.10.20")
        sensors = load_sensors_from_json("labjack_channels.json", board="T7")
        thread = Thread(target=t7.stream, args=(sensors,), daemon=True)
        thread.start()
        global command_executor
        ce = CommandExecutor(t7.handle)
        command_executor = ce
    except AttributeError:
        logger.warn(
            "Unable to open labjack due to not having the right libraries and drivers"
        )
    except LJMError:
        logger.warn("Unable to open t7 labjack through ethernet")

    lj_test = LabJackTest(loop)
    lj_test.init()
