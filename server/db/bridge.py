import os
import json
import time
import threading
import paho.mqtt.client as mqtt
from influxdb_client_3 import InfluxDBClient3, Point


class Bridge:
    def __init__(self, url, token, database_name, host, port):
        # ========== ENV CONFIG ==========
        self.influx_url = url
        self.influx_token = token
        self.influx_database = database_name

        self.mqtt_host = host
        self.mqtt_port = int(port)

        self.BATCH_SIZE = 50
        self.FLUSH_INTERVAL = 5  # seconds

        # ========== CONNECT TO INFLUX ==========
        self.client = InfluxDBClient3(
            host=self.influx_url,
            token=self.influx_token,
            database=self.influx_database,
        )

        # ========== BATCH STORAGE ==========
        self.batch = []
        self.batch_lock = threading.Lock()

        self.shutdown_event = threading.Event()

        # Keys that should always be tags
        self.TAG_KEYS = {"device", "location", "site"}

    def start(self):
        # ========== START FLUSH THREAD ==========
        self.flush_thread = threading.Thread(target=self.flush_batch, daemon=True)
        self.flush_thread.start()

        # ========== START MQTT ==========
        self.mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        self.mqtt_client.on_connect = self.on_connect
        self.mqtt_client.on_message = self.on_message

        self.mqtt_client.connect(self.mqtt_host, self.mqtt_port, 60)
        self.mqtt_client.loop_start()

    # ========== SCHEMA HANDLER ==========
    def build_point_from_payload(self, payload):
        measurement = payload.get("measurement", "labjack")

        point = Point(measurement)

        for key, value in payload.items():
            if key == "measurement":
                continue

            if value is None:
                continue

            # Tag handling
            if key in self.TAG_KEYS:
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
    def flush_batch(self):
        while not self.shutdown_event.is_set():
            time.sleep(self.FLUSH_INTERVAL)

            with self.batch_lock:
                if self.batch:
                    try:
                        self.client.write(self.batch)
                        print(f"Flushed {len(self.batch)} points")
                        self.batch = []
                    except Exception as e:
                        print("Flush error:", e)

    # ========== MQTT CALLBACKS ==========
    def on_connect(self, client, userdata, flags, reason_code, properties):
        print("Connected to MQTT", reason_code)
        client.subscribe("labjack/#")

    def on_message(self, client_mqtt, userdata, msg):
        try:
            payload = json.loads(msg.payload.decode())
            point = self.build_point_from_payload(payload)

            with self.batch_lock:
                self.batch.append(point)

                if len(self.batch) >= self.BATCH_SIZE:
                    self.client.write(self.batch)
                    print(f"Wrote batch of {len(self.batch)}")
                    self.batch = []

        except Exception as e:
            print("Message error:", e)

    # ========== SHUTDOWN FUNCTION ==========
    def shutdown(self):
        print("[Bridge] shutting down...")

        self.shutdown_event.set()

        try:
            self.mqtt_client.loop_stop()
        except Exception:
            pass

        try:
            self.client.close()
        except Exception:
            pass

        print("[Bridge] shutdown complete")


# vim: et:sw=4
