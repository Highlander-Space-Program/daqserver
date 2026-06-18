from threading import Lock
from types import SimpleNamespace

from server.mqtt import ControlPublisher


def make_publisher() -> ControlPublisher:
    publisher = ControlPublisher.__new__(ControlPublisher)
    publisher._breakwire_status = "unknown"
    publisher._breakwire_lock = Lock()
    return publisher


def publish_breakwire_payload(
    publisher: ControlPublisher,
    payload: bytes,
    topic: str = ControlPublisher.BREAKWIRE_TOPIC,
) -> None:
    message = SimpleNamespace(topic=topic, payload=payload)
    publisher._on_message(None, None, message)


def test_breakwire_connected_sets_status():
    publisher = make_publisher()

    publish_breakwire_payload(publisher, bytes([0x10]))

    assert publisher.get_breakwire_status() == {"status": "connected"}


def test_breakwire_broken_sets_status():
    publisher = make_publisher()

    publish_breakwire_payload(publisher, bytes([0x11]))

    assert publisher.get_breakwire_status() == {"status": "broken"}


def test_text_breakwire_payload_does_not_change_status():
    publisher = make_publisher()
    publish_breakwire_payload(publisher, bytes([0x10]))

    publish_breakwire_payload(publisher, b"connected")

    assert publisher.get_breakwire_status() == {"status": "connected"}


def test_invalid_breakwire_payload_does_not_change_status():
    publisher = make_publisher()
    publish_breakwire_payload(publisher, bytes([0x10]))

    publish_breakwire_payload(publisher, bytes([0x12]))

    assert publisher.get_breakwire_status() == {"status": "connected"}


def test_multi_byte_breakwire_payload_does_not_change_status():
    publisher = make_publisher()
    publish_breakwire_payload(publisher, bytes([0x10]))

    publish_breakwire_payload(publisher, bytes([0x10, 0x11]))

    assert publisher.get_breakwire_status() == {"status": "connected"}


def test_non_breakwire_topic_does_not_change_status():
    publisher = make_publisher()

    publish_breakwire_payload(publisher, bytes([0x11]), topic="device/other")

    assert publisher.get_breakwire_status() == {"status": "unknown"}


def test_missing_mqtt_host_disables_publisher(monkeypatch):
    monkeypatch.delenv("MQTT_HOST", raising=False)

    publisher = ControlPublisher()

    assert publisher.is_connected is False
    assert publisher.get_breakwire_status() == {"status": "unknown"}
    assert publisher.send_command(1) is False

    publisher.shutdown()


def test_unreachable_mqtt_host_disables_publisher(monkeypatch):
    class FailingClient:
        def __init__(self, *args, **kwargs):
            pass

        def connect(self, host, port):
            raise OSError("getaddrinfo failed")

    monkeypatch.setenv("MQTT_HOST", "mosquitto")
    monkeypatch.setenv("MQTT_PORT", "1883")
    monkeypatch.setattr("server.mqtt.mqtt.Client", FailingClient)

    publisher = ControlPublisher()

    assert publisher.is_connected is False
    assert publisher.send_command(1) is False

    publisher.shutdown()
