from server.streaming.sensors import T7ID, InputId, TestID

PORT_OPTIONS: dict[str, InputId] = {
    "PT-1": T7ID(4, "AIN8"),
    "PT-2": T7ID(4, "AIN9"),
    "PT-3": T7ID(4, "AIN10"),
    "PT-4": T7ID(4, "AIN11"),
    "TC-1": T7ID(3, "AIN0"),
    "TC-2": T7ID(3, "AIN1"),
    "TC-3": T7ID(3, "AIN2"),
    "LC-1": T7ID(3, "AIN4"),
    "test": TestID(),
}

DB_PATH = "daq_ui.db"

PIN_MAPPING = {
    # --- AIN13 row ---
    # Negative channel: 53N
    "AIN61": {"mux": 3, "cb37_pin": "AIN13"},
    "AIN85": {"mux": 4, "cb37_pin": "AIN13"},
    # Negative channel: 101N
    "AIN109": {"mux": 5, "cb37_pin": "AIN13"},
    # --- AIN12 row ---
    # Negative channel: 52N
    "AIN60": {"mux": 3, "cb37_pin": "AIN12"},
    "AIN84": {"mux": 4, "cb37_pin": "AIN12"},
    # Negative channel: 100N
    "AIN108": {"mux": 5, "cb37_pin": "AIN12"},
    # --- AIN11 row ---
    # Negative channel: 119N
    "AIN127": {"mux": 2, "cb37_pin": "AIN11"},
    # Negative channel: 51N
    "AIN59": {"mux": 3, "cb37_pin": "AIN11"},
    "AIN83": {"mux": 4, "cb37_pin": "AIN11"},
    # Negative channel: 99N
    "AIN107": {"mux": 5, "cb37_pin": "AIN11"},
    # --- AIN10 row ---
    # Negative channel: 118N
    "AIN126": {"mux": 2, "cb37_pin": "AIN10"},
    # Negative channel: 50N
    "AIN58": {"mux": 3, "cb37_pin": "AIN10"},
    "AIN82": {"mux": 4, "cb37_pin": "AIN10"},
    # Negative channel: 98N
    "AIN106": {"mux": 5, "cb37_pin": "AIN10"},
    # --- AIN9 row ---
    # Negative channel: 117N
    "AIN125": {"mux": 2, "cb37_pin": "AIN9"},
    # Negative channel: 49N
    "AIN57": {"mux": 3, "cb37_pin": "AIN9"},
    "AIN81": {"mux": 4, "cb37_pin": "AIN9"},
    # Negative channel: 97N
    "AIN105": {"mux": 5, "cb37_pin": "AIN9"},
    # --- AIN8 row ---
    # Negative channel: 116N
    "AIN124": {"mux": 2, "cb37_pin": "AIN8"},
    # Negative channel: 48N
    "AIN56": {"mux": 3, "cb37_pin": "AIN8"},
    "AIN80": {"mux": 4, "cb37_pin": "AIN8"},
    # Negative channel: 96N
    "AIN104": {"mux": 5, "cb37_pin": "AIN8"},
    # --- AIN7 row ---
    # Negative channel: 115N
    "AIN123": {"mux": 2, "cb37_pin": "AIN7"},
    "AIN55": {"mux": 3, "cb37_pin": "AIN7"},
    # Negative channel: 71N
    "AIN79": {"mux": 4, "cb37_pin": "AIN7"},
    "AIN103": {"mux": 5, "cb37_pin": "AIN7"},
    # --- AIN6 row ---
    # Negative channel: 114N
    "AIN122": {"mux": 2, "cb37_pin": "AIN6"},
    "AIN54": {"mux": 3, "cb37_pin": "AIN6"},
    # Negative channel: 70N
    "AIN78": {"mux": 4, "cb37_pin": "AIN6"},
    "AIN102": {"mux": 5, "cb37_pin": "AIN6"},
    # --- AIN5 row ---
    # Negative channel: 113N
    "AIN121": {"mux": 2, "cb37_pin": "AIN5"},
    "AIN53": {"mux": 3, "cb37_pin": "AIN5"},
    # Negative channel: 69N
    "AIN77": {"mux": 4, "cb37_pin": "AIN5"},
    "AIN101": {"mux": 5, "cb37_pin": "AIN5"},
    # --- AIN4 row ---
    # Negative channel: 112N
    "AIN120": {"mux": 2, "cb37_pin": "AIN4"},
    "AIN52": {"mux": 3, "cb37_pin": "AIN4"},
    # Negative channel: 68N
    "AIN76": {"mux": 4, "cb37_pin": "AIN4"},
    "AIN100": {"mux": 5, "cb37_pin": "AIN4"},
    # --- AIN3 row ---
    # Negative channel: 2N
    "AIN3": {"mux": 2, "cb37_pin": "AIN3"},
    "AIN51": {"mux": 3, "cb37_pin": "AIN3"},
    # Negative channel: 67N
    "AIN75": {"mux": 4, "cb37_pin": "AIN3"},
    "AIN99": {"mux": 5, "cb37_pin": "AIN3"},
    # --- AIN2 row ---
    "AIN2": {"mux": 2, "cb37_pin": "AIN2"},
    "AIN50": {"mux": 3, "cb37_pin": "AIN2"},
    # Negative channel: 66N
    "AIN74": {"mux": 4, "cb37_pin": "AIN2"},
    "AIN98": {"mux": 5, "cb37_pin": "AIN2"},
    # --- AIN1 row ---
    # Negative channel: 0N
    "AIN1": {"mux": 2, "cb37_pin": "AIN1"},
    "AIN49": {"mux": 3, "cb37_pin": "AIN1"},
    # Negative channel: 65N
    "AIN73": {"mux": 4, "cb37_pin": "AIN1"},
    "AIN97": {"mux": 5, "cb37_pin": "AIN1"},
    # --- AIN0 row ---
    "AIN0": {"mux": 2, "cb37_pin": "AIN0"},
    "AIN48": {"mux": 3, "cb37_pin": "AIN0"},
    # Negative channel: 64N
    "AIN72": {"mux": 4, "cb37_pin": "AIN0"},
    "AIN96": {"mux": 5, "cb37_pin": "AIN0"},
    # --- Non-AIN Rows (MIO, PIN) ---
    "MIO0": {"mux": 2, "cb37_pin": "MIO0"},
    "MIO1": {"mux": 2, "cb37_pin": "MIO1"},
    "MIO2": {"mux": 2, "cb37_pin": "MIO2"},
    "PIN2": {"mux": 2, "cb37_pin": "PIN2"},
    "PIN20": {"mux": 2, "cb37_pin": "PIN20"},
    # --- FIO7 row ---
    "FIO7": {"mux": 2, "cb37_pin": "FIO7"},
    "AIN71": {"mux": 3, "cb37_pin": "FIO7"},
    # Negative channel: 87N
    "AIN95": {"mux": 4, "cb37_pin": "FIO7"},
    "AIN119": {"mux": 5, "cb37_pin": "FIO7"},
    # --- FIO6 row ---
    "FIO6": {"mux": 2, "cb37_pin": "FIO6"},
    "AIN70": {"mux": 3, "cb37_pin": "FIO6"},
    # Negative channel: 86N
    "AIN94": {"mux": 4, "cb37_pin": "FIO6"},
    "AIN118": {"mux": 5, "cb37_pin": "FIO6"},
    # --- FIO5 row ---
    "FIO5": {"mux": 2, "cb37_pin": "FIO5"},
    "AIN69": {"mux": 3, "cb37_pin": "FIO5"},
    # Negative channel: 85N
    "AIN93": {"mux": 4, "cb37_pin": "FIO5"},
    "AIN117": {"mux": 5, "cb37_pin": "FIO5"},
    # --- FIO4 row ---
    "FIO4": {"mux": 2, "cb37_pin": "FIO4"},
    "AIN68": {"mux": 3, "cb37_pin": "FIO4"},
    # Negative channel: 84N
    "AIN92": {"mux": 4, "cb37_pin": "FIO4"},
    "AIN116": {"mux": 5, "cb37_pin": "FIO4"},
    # --- FIO3 row ---
    "FIO3": {"mux": 2, "cb37_pin": "FIO3"},
    "AIN67": {"mux": 3, "cb37_pin": "FIO3"},
    # Negative channel: 83N
    "AIN91": {"mux": 4, "cb37_pin": "FIO3"},
    "AIN115": {"mux": 5, "cb37_pin": "FIO3"},
    # --- FIO2 row ---
    "FIO2": {"mux": 2, "cb37_pin": "FIO2"},
    "AIN66": {"mux": 3, "cb37_pin": "FIO2"},
    # Negative channel: 82N
    "AIN90": {"mux": 4, "cb37_pin": "FIO2"},
    "AIN114": {"mux": 5, "cb37_pin": "FIO2"},
    # --- FIO1 row ---
    "FIO1": {"mux": 2, "cb37_pin": "FIO1"},
    "AIN65": {"mux": 3, "cb37_pin": "FIO1"},
    # Negative channel: 81N
    "AIN89": {"mux": 4, "cb37_pin": "FIO1"},
    "AIN113": {"mux": 5, "cb37_pin": "FIO1"},
    # --- FIO0 row ---
    "FIO0": {"mux": 2, "cb37_pin": "FIO0"},
    "AIN64": {"mux": 3, "cb37_pin": "FIO0"},
    # Negative channel: 80N
    "AIN88": {"mux": 4, "cb37_pin": "FIO0"},
    "AIN112": {"mux": 5, "cb37_pin": "FIO0"},
    # --- DAC1 row ---
    "DAC1": {"mux": 2, "cb37_pin": "DAC1"},
    # Negative channel: 55N
    "AIN63": {"mux": 3, "cb37_pin": "DAC1"},
    "AIN87": {"mux": 4, "cb37_pin": "DAC1"},
    # Negative channel: 103N
    "AIN111": {"mux": 5, "cb37_pin": "DAC1"},
    # --- DAC0 row ---
    "DAC0": {"mux": 2, "cb37_pin": "DAC0"},
    # Negative channel: 54N
    "AIN62": {"mux": 3, "cb37_pin": "DAC0"},
    "AIN86": {"mux": 4, "cb37_pin": "DAC0"},
    # Negative channel: 102N
    "AIN110": {"mux": 5, "cb37_pin": "DAC0"},
}
