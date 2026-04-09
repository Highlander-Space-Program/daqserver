import os
import json
import time
import threading
import paho.mqtt.client as mqtt
from influxdb_client_3 import InfluxDBClient3, Point

# ========== ENV CONFIG ==========
INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_DATABASE = os.getenv("INFLUX_DATABASE")

MQTT_HOST = os.getenv("MQTT_HOST")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))

BATCH_SIZE = 50
FLUSH_INTERVAL = 5  # seconds

# ========== CONNECT TO INFLUX ==========
client = InfluxDBClient3(
    host=INFLUX_URL,
    token=INFLUX_TOKEN,
    database=INFLUX_DATABASE
)

# ========== BATCH STORAGE ==========
batch = []
batch_lock = threading.Lock()

# Keys that should always be tags
TAG_KEYS = {"device", "location", "site"}

# ========== SCHEMA HANDLER ==========
def build_point_from_payload(payload):
    measurement = payload.get("measurement", "labjack")

    point = Point(measurement)

    for key, value in payload.items():
        if key == "measurement":
            continue

        if value is None:
            continue

        # Tag handling
        if key in TAG_KEYS:
            point.tag(key, str(value))
            continue

        # Automatic numeric detection
        if isinstance(value, (int, float)):
            point.field(key, value)

        # Boolean
        elif isinstance(value, bool):
            point.field(key, value)

        # String
        elif isinstance(value, str):
            # If small set of strings → often better as tag
            if len(value) < 32:
                point.tag(key, value)
            else:
                point.field(key, value)

        # Ignore complex types (arrays, dicts)
        else:
            continue

    return point

# ========== FLUSH FUNCTION ==========
def flush_batch():
    global batch
    while True:
        time.sleep(FLUSH_INTERVAL)

        with batch_lock:
            if batch:
                try:
                    client.write(batch)
                    print(f"Flushed {len(batch)} points")
                    batch = []
                except Exception as e:
                    print("Flush error:", e)

# ========== MQTT CALLBACKS ==========
def on_connect(client, userdata, flags, reason_code, properties):
    print("Connected to MQTT", reason_code)
    client.subscribe("labjack/#")

def on_message(client_mqtt, userdata, msg):
    global batch

    try:
        payload = json.loads(msg.payload.decode())
        point = build_point_from_payload(payload)

        with batch_lock:
            batch.append(point)

            if len(batch) >= BATCH_SIZE:
                client.write(batch)
                print(f"Wrote batch of {len(batch)}")
                batch = []

    except Exception as e:
        print("Message error:", e)

# ========== START FLUSH THREAD ==========
flush_thread = threading.Thread(target=flush_batch, daemon=True)
flush_thread.start()

# ========== START MQTT ==========
mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
mqtt_client.on_connect = on_connect
mqtt_client.on_message = on_message

mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
mqtt_client.loop_forever()
