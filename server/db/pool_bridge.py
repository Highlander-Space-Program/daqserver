import threading
import time
import asyncio
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

        # ========== ASYNC ==========
        self.queue = asyncio.Queue()
        self.flush_task = None
        self.running = False

        self.BATCH_SIZE = 50
        self.FLUSH_INTERVAL = 5

        # optional tagging rules
        self.TAG_KEYS = {"device", "location", "site"}

    # ========== START ==========
    def start(self):
        self.running = True

        # subscribe to datapool
        self.datapool.subscribe("SENSORDATA", self.handle_data)

        # start async flush loop
        loop = asyncio.get_running_loop()
        self.flush_task = loop.create_task(self.flush_loop())

        print("PoolBridge started")

    # ========== CALLBACK (ASYNC) ==========
    def handle_data(self, data):
        """
        Receives datapool events (async callback)
        Converts to Influx Point
        """

        try:
            points = self.normalize(data)

            for p in points:
                self.queue.put_nowait(p)

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
    async def flush_loop(self):
        batch = []

        try:
            while self.running:
                try:
                    # wait for next item with timeout
                    item = await asyncio.wait_for(
                        self.queue.get(),
                        timeout=self.FLUSH_INTERVAL
                    )
                    batch.append(item)

                    if len(batch) >= self.BATCH_SIZE:
                        await self.flush(batch)
                        batch = []

                except asyncio.TimeoutError:
                    # time-based flush
                    if batch:
                        await self.flush(batch)
                        batch = []

        except asyncio.CancelledError:
            # flush remaining on shutdown
            if batch:
                await self.flush(batch)
            raise

    # ========== FLUSH ==========
    async def flush(self, batch):
        try:
            # run blocking write in thread
            await asyncio.to_thread(self.client.write, batch)
            print(f"[PoolBridge] wrote {len(batch)}")
        except Exception as e:
            print("[PoolBridge write error]:", e)

    # ========== SHUTDOWN ==========
    async def shutdown(self):
        print("[PoolBridge] shutting down...")

        self.running = False

        if self.flush_task:
            self.flush_task.cancel()
            try:            
                await self.flush_task
            except asyncio.CancelledError:
                pass

        # close client
        try:
            await asyncio.to_thread(self.client.close)
        except Exception:
            pass

        print("[PoolBridge] shutdown complete")


