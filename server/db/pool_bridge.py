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

        # for shutdown
        self.shutdown_event = threading.Event()

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
    def handle_data(self, data):
        """
        Receives datapool events (async callback)
        Converts to Influx Point
        """

        try:
            points = self.normalize(data)

            with self.batch_lock:
                self.batch.extend(points)

                if len(self.batch) >= self.BATCH_SIZE:
                    self.flush_batch()

        except Exception as e:
            print("[PoolBridge] error:", e)

    # ========== NORMALIZE DATA  ==========
    def normalize(self, data):
        """
        Converts any datapool payload into Influx Points
        Supports dict, list, or structured objects
        """

        if isinstance(data, list):
            return [self.build_point(d) for d in data]

        if hasattr(data, "to_dict"):
            data = data.to_dict()

        if isinstance(data, dict):
            return [self.build_point(data)]

        raise ValueError(f"Unsupported datapool format: {type(data)}")

    # ========== POINT BUILDER ==========
    def build_point(self, payload):
        measurement = payload.get("measurement", "datapool")
        point = Point(measurement)

        for key, value in payload.items():
            if key == "measurement" or value is None:
                continue

            if key in self.TAG_KEYS:
                point.tag(key, str(value))
            elif isinstance(value, (int, float, bool)):
                point.field(key, value)
            else:
                point.tag(key, str(value))

        return point

    # ========== FLUSH LOOP ==========
    def flush_loop(self):
        while not self.shutdown_event.is_set():
            time.sleep(self.FLUSH_INTERVAL)

            with self.batch_lock:
                self.flush_batch()

    def flush_batch(self):
        if not self.batch:
            return

        try:
            self.client.write(self.batch)
            print(f"[PoolBridge] wrote {len(self.batch)}")
            self.batch = []

        except Exception as e:
            print("[PoolBridge write error]:", e)

    # ========== SHUTDOWN ==========
    def shutdown(self):
        print("[PoolBridge] shutting down... flushing remaining data")

        self.shutdown_event.set()

        with self.batch_lock:
            try:            
                self.flush_batch()
            except Exception as e:
                print("[PoolBridge shutdown flush error]:", e)

        try:
            self.client.close()
        except Exception:
            pass

        print("[PoolBridge] shutdown complete")


