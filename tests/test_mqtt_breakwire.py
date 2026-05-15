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

    publish_breakwire_payload(publisher, b"connected")

    assert publisher.get_breakwire_status() == {"status": "connected"}


def test_breakwire_broken_sets_status():
    publisher = make_publisher()

    publish_breakwire_payload(publisher, b"broken")

    assert publisher.get_breakwire_status() == {"status": "broken"}


def test_breakwire_status_normalizes_whitespace_and_case():
    publisher = make_publisher()

    publish_breakwire_payload(publisher, b" Connected ")

    assert publisher.get_breakwire_status() == {"status": "connected"}


def test_invalid_breakwire_payload_does_not_change_status():
    publisher = make_publisher()
    publish_breakwire_payload(publisher, b"connected")

    publish_breakwire_payload(publisher, b"offline")

    assert publisher.get_breakwire_status() == {"status": "connected"}


def test_non_breakwire_topic_does_not_change_status():
    publisher = make_publisher()

    publish_breakwire_payload(publisher, b"broken", topic="device/other")

    assert publisher.get_breakwire_status() == {"status": "unknown"}
