import threading
import time
from influxdb_client_3 import InfluxDBClient3, Point


class PoolBridge:
    def __init__(self, datapool, url, token, database_name):
        # ========== INFLUX CONFIG ==========
        self.influx_url = url
        self.influx_token = token
        self.influx_database = database_name

        self.client = InfluxDBClient3(
            host=self.influx_url,
            token=self.influx_token,
            database=self.influx_database
        )

        # ========== DATAPOOL ==========
        self.datapool = datapool

        # ========== BATCH ==========
        self.batch = []
        self.batch_lock = threading.Lock()

        self.BATCH_SIZE = 50
        self.FLUSH_INTERVAL = 5

        # optional tagging rules
        self.TAG_KEYS = {"device", "location", "site"}

    # ========== START ==========
    def start(self):
        # subscribe to datapool
        self.datapool.subscribe("SENSORDATA", self.handle_data)

        # start flush thread
        self.flush_thread = threading.Thread(
            target=self.flush_loop,
            daemon=True
        )
        self.flush_thread.start()

        print("PoolBridge started")

    # ========== CALLBACK (ASYNC) ==========
    async def handle_data(self, data):
        """
        Receives datapool events (async callback)
        Converts to Influx Point
        """

        try:
            point = self.build_point(data)

            with self.batch_lock:
                self.batch.append(point)

                if len(self.batch) >= self.BATCH_SIZE:
                    self.client.write(self.batch)
                    print(f"[PoolBridge] wrote batch {len(self.batch)}")
                    self.batch = []

        except Exception as e:
            print("[PoolBridge] error:", e)

    # ========== POINT BUILDER ==========
    def build_point(self, payload):
        measurement = payload.get("measurement", "datapool")
        point = Point(measurement)

        for key, value in payload.items():
            if key == "measurement" or value is None:
                continue

            if key in self.TAG_KEYS:
                point.tag(key, str(value))
                continue

            if isinstance(value, (int, float)):
                point.field(key, value)

            elif isinstance(value, bool):
                point.field(key, value)

            elif isinstance(value, str):
                if len(value) < 32:
                    point.tag(key, value)
                else:
                    point.field(key, value)

        return point

    # ========== FLUSH LOOP ==========
    def flush_loop(self):
        while True:
            time.sleep(self.FLUSH_INTERVAL)

            with self.batch_lock:
                if self.batch:
                    try:
                        self.client.write(self.batch)
                        print(f"[PoolBridge] flushed {len(self.batch)}")
                        self.batch = []
                    except Exception as e:
                        print("[PoolBridge flush error]:", e)
