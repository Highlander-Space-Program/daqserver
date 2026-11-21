import asyncio
import itertools
import json
from threading import Lock
from types import SimpleNamespace

import pytest

from server.mqtt import (
    CommandRejected,
    CommandTimeout,
    ControlPublisher,
    PublisherUnavailable,
)


class RecordingClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos):
        self.published.append((topic, json.loads(payload)))


def make_publisher(client=None) -> ControlPublisher:
    publisher = ControlPublisher.__new__(ControlPublisher)
    publisher._breakwire_status = "unknown"
    publisher._breakwire_lock = Lock()
    publisher._pending = {}
    publisher._pending_lock = Lock()
    publisher._command_ids = itertools.count(1)
    publisher.client = client
    return publisher


def publish_breakwire_payload(
    publisher: ControlPublisher,
    payload: bytes,
    topic: str = ControlPublisher.BREAKWIRE_TOPIC,
) -> None:
    message = SimpleNamespace(topic=topic, payload=payload)
    publisher._on_message(None, None, message)


def publish_response(publisher: ControlPublisher, response) -> None:
    payload = response if isinstance(response, bytes) else json.dumps(response)
    publish_breakwire_payload(
        publisher, payload, topic=ControlPublisher.RESPONSE_TOPIC
    )


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


def test_send_command_publishes_json_and_returns_ok_response():
    client = RecordingClient()
    publisher = make_publisher(client)

    async def scenario():
        task = asyncio.create_task(publisher.send_command(0x06))
        await asyncio.sleep(0)
        publish_response(publisher, {"id": 1, "status": "Ok", "message": ""})
        return await task

    response = asyncio.run(scenario())

    assert client.published == [
        (ControlPublisher.COMMAND_TOPIC, {"command": 0x06, "id": 1})
    ]
    assert response == {"id": 1, "status": "Ok", "message": ""}
    assert publisher._pending == {}


def test_send_command_raises_rejected_with_board_message():
    publisher = make_publisher(RecordingClient())

    async def scenario():
        task = asyncio.create_task(publisher.send_command(0x06))
        await asyncio.sleep(0)
        publish_response(
            publisher, {"id": 1, "status": "Error", "message": "servo jammed"}
        )
        return await task

    with pytest.raises(CommandRejected) as exc_info:
        asyncio.run(scenario())

    assert exc_info.value.message == "servo jammed"
    assert exc_info.value.command_id == 1


def test_send_command_times_out_without_response():
    publisher = make_publisher(RecordingClient())

    with pytest.raises(CommandTimeout) as exc_info:
        asyncio.run(publisher.send_command(0x06, timeout=0.01))

    assert exc_info.value.command_id == 1
    assert publisher._pending == {}


def test_responses_are_matched_by_id():
    publisher = make_publisher(RecordingClient())

    async def scenario():
        first = asyncio.create_task(publisher.send_command(0x06))
        second = asyncio.create_task(publisher.send_command(0x08))
        await asyncio.sleep(0)
        publish_response(publisher, {"id": 2, "status": "Ok", "message": "b"})
        publish_response(publisher, {"id": 1, "status": "Ok", "message": "a"})
        return await first, await second

    first, second = asyncio.run(scenario())

    assert first["message"] == "a"
    assert second["message"] == "b"


@pytest.mark.parametrize(
    "payload",
    [b"not json", b'{"status": "Ok"}', b'{"id": 99, "status": "Ok"}'],
)
def test_bad_or_unknown_responses_are_ignored(payload):
    publisher = make_publisher(RecordingClient())

    publish_response(publisher, payload)

    assert publisher._pending == {}


def test_missing_mqtt_host_disables_publisher(monkeypatch):
    monkeypatch.delenv("MQTT_HOST", raising=False)

    publisher = ControlPublisher()

    assert publisher.is_connected is False
    assert publisher.get_breakwire_status() == {"status": "unknown"}
    with pytest.raises(PublisherUnavailable):
        asyncio.run(publisher.send_command(1))

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
    with pytest.raises(PublisherUnavailable):
        asyncio.run(publisher.send_command(1))

    publisher.shutdown()
