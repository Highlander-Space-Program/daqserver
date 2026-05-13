import os
import paho.mqtt.client as mqtt

class ControlPublisher:
    def __init__(self):
        mqtt_host = os.getenv("MQTT_HOST")
        mqtt_port = int(os.getenv("MQTT_PORT", 1883))

        if mqtt_host is None:
            raise RuntimeError("MQTT_HOST environment variable is required")

        self.client = mqtt.Client()
        self.client.connect(mqtt_host, mqtt_port)
        self.client.loop_start()

    def send_command(self, control_cmd):
        self.client.publish("device/command", payload=bytes([control_cmd]), qos=2)

    def shutdown(self):
        self.client.loop_stop()
        self.client.disconnect()