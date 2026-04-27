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
        self.TAG_KEYS = {"device", "location", "site", "mux_number", "ain", "type"}

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
            return [p for d in data for p in self.normalize(d)]

        if hasattr(data, "get_data"):
            return self.from_sensor_output(data.get_data())

        if hasattr(data, "to_dict"):
            data = data.to_dict()

        if isinstance(data, dict):
            if "channels" in data:
                return self.from_channels(data)

            return [self.build_point(data)]

        raise ValueError(f"Unsupported datapool format: {type(data)}")
        
    # ========== MORE DATA HANDLING ==========
    def get_measurement(self, name: str | None, fallback="sensor"):
        if not name:
            return fallback
        return str(name).lower()

    
    def get_measurement(self, name: str | None, fallback="sensor"):
        if not name:
            return fallback
        return str(name).lower()    


    def from_channels(self, packet: dict):
        points = []

        base_tags = {
            k: v for k, v in packet.items()
            if k != "channels"
        }

        channels = packet.get("channels", {})

        for ain, ch in channels.items():
            measurement = self.get_measurement(ch.get("sensor_type"))
            point = Point(measurement)

            # identity schema
            self.apply_identity_tags(point, {
                "device": base_tags.get("device"),
                "location": base_tags.get("location"),
                "channel": ain,
                "mux_number": ch.get("mux_number"),
                "ain": ain,
            })

            # field standardization
            if "value" in ch and isinstance(ch["value"], (int, float)):
                point.field("value", ch["value"])
            elif "voltage" in ch and isinstance(ch["voltage"], (int, float)):
                point.field("value", ch["voltage"])

            # optional timestamp
            if "timestamp" in base_tags:
                self.apply_timestamp(point, base_tags["timestamp"])

            points.append(point)

        return points

    # ========== SENSOR OUTPUT FORMAT ==========
    def from_sensor_output(self, sensor_output):
        points = []

        source = sensor_output.source.to_dict()
        measurement = self.get_measurement(sensor_output.data_type.value)

        for entry in sensor_output.data:
            point = Point(measurement)  # measurement = type (TC, PT, etc.)

            self.apply_identity_tags(point, source)
            point.tag("data_type", measurement)

            point.fielt("value", entry.value)
            point.time(entry.time)

            points.append(point)

        return points

    def apply_timestamp(self, point, t):
        try:
            if t:
                point.time(t)
        except Exception:
            pass

    # ========== POINT BUILDER ==========
    def build_point(self, payload):
        measurement = self.get_measurement(payload.get("measurement"))
        point = Point(measurement)

        self.apply_identity_tags(
            point,
            {k: v for k, v in payload.items() if k in self.TAG_KEYS}
        )
        
        for key, value in payload.items():
            if key == "measurement" or value is None:
                continue

            elif isinstance(value, (int, float, bool)):
                if key == "value":
                    point.field("value", value)
                else:
                    point.field(key, value)

            elif isinstance(value, str):
                point.tag(key, value)

            elif isinstance(value, dict):
                pass  # intentionally ignored (prevents schema explosion)

            elif isinstance(value, list):
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


