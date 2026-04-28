from server.streaming.sensors import T7ID, InputId, TestID

PORT_OPTIONS: dict[str, InputId] = {
    "PT-1": T7ID(0, 52),
    "PT-2": T7ID(1, 60),
    "PT-3": T7ID(0, 48),
    "TC-1": T7ID(0, 50),
    "TC-2": T7ID(4, 10),
    "TC-3": T7ID(4, 10),
    "test": TestID(),
}

DB_PATH = "daq_ui.db"
