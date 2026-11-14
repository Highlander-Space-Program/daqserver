import time
import random
import threading
from datetime import datetime
from influxdb_client_3 import InfluxDBClient3, Point
import os

def load_env():
    env = {}
    with open(".env") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                env[k] = v
    return env

env = load_env()

INFLUX_URL = env["INFLUXDB_URL"]
INFLUX_TOKEN = env["INFLUXDB_TOKEN"]
DATABASE = env["INFLUXDB_DATABASE"]

POINTS_PER_BATCH = 20000
BATCHES_PER_SECOND = 10   # 5000 * 20 = 100k pts/sec
THREADS = 2               # increase for more load

# ========= SENSOR DEFINITIONS =========
SENSORS = [
    # Thermocouples
    ("thermocouple", 3, "AIN48"),
    ("thermocouple", 3, "AIN49"),
    ("thermocouple", 3, "AIN50"),

    # Pressure transducers
    ("pressuretransducer", 4, "AIN80"),
    ("pressuretransducer", 4, "AIN81"),
    ("pressuretransducer", 4, "AIN82"),
    ("pressuretransducer", 4, "AIN83"),

    # Load cell
    ("loadcell", 3, "AIN52"),
]

client = InfluxDBClient3(
    host=INFLUX_URL,
    token=INFLUX_TOKEN,
    database=DATABASE,
)

def generate_batch():
    now = datetime.utcnow()
    points = []

    for _ in range(POINTS_PER_BATCH):
        sensor = random.choice(SENSORS)
        measurement, mux, ain = sensor

        value = random.uniform(0, 5)

        p = (
            Point(measurement)
            .tag("mux_number", str(mux))
            .tag("ain", ain)
            .tag("type", "T7")
            .field("value", value)
            .time(now)
        )

        points.append(p)

    return points


def worker():
    interval = 1.0 / BATCHES_PER_SECOND

    while True:
        start = time.time()

        batch = generate_batch()
        client.write(batch)

        elapsed = time.time() - start
        sleep_time = max(0, interval - elapsed)

        if sleep_time > 0:
            time.sleep(sleep_time)


# ========= RUN =========
if __name__ == "__main__":
    print("Starting stress test...")
    print(f"Target rate ≈ {POINTS_PER_BATCH * BATCHES_PER_SECOND * THREADS} pts/sec")

    threads = []
    for _ in range(THREADS):
        t = threading.Thread(target=worker, daemon=True)
        t.start()
        threads.append(t)

    while True:
        time.sleep(5)
        print("Still running...")
