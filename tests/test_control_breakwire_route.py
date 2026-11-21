from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from server.mqtt import CommandRejected, CommandTimeout, PublisherUnavailable
from server.web.routes import control
from server.web.routes.control import router, state


class FakeControlPublisher:
    def __init__(self, breakwire_status="broken"):
        self.breakwire_status = breakwire_status

    def get_breakwire_status(self):
        return {"status": self.breakwire_status}


class DisabledControlPublisher(FakeControlPublisher):
    async def send_command(self, command: int, timeout: float = 3.0):
        raise PublisherUnavailable(
            "MQTT control publisher is not connected", command, None
        )


class RecordingControlPublisher(FakeControlPublisher):
    def __init__(self):
        super().__init__()
        self.commands = []

    async def send_command(self, command: int, timeout: float = 3.0):
        self.commands.append(command)
        return {"id": len(self.commands), "status": "Ok", "message": ""}


class FailingControlPublisher(FakeControlPublisher):
    def __init__(self, error_cls, message):
        super().__init__()
        self.error_cls = error_cls
        self.message = message

    async def send_command(self, command: int, timeout: float = 3.0):
        raise self.error_cls(self.message, command, 7)


def make_client(publisher):
    app = FastAPI()
    app.state.control_publisher = publisher
    app.include_router(router)
    return TestClient(app)


def reset_servo_state():
    for servo in state["servos"]:
        servo["status"] = "CLOSED"
    state["event_log"] = []


def test_breakwire_route_returns_current_status():
    response = make_client(FakeControlPublisher()).get(
        "/controls/api/breakwire"
    )

    assert response.status_code == 200
    assert response.json() == {"status": "broken"}


def test_status_route_uses_control_publisher_breakwire_status():
    response = make_client(FakeControlPublisher("connected")).get(
        "/controls/api/status"
    )

    assert response.status_code == 200
    assert response.json()["breakwire"] == {
        "status": "connected",
        "connected": True,
    }


def test_command_route_returns_unavailable_when_mqtt_is_disabled():
    response = make_client(DisabledControlPublisher()).post(
        "/controls/api/command",
        json={"command": 1},
    )

    assert response.status_code == 503
    assert response.json() == {
        "detail": "MQTT control publisher is not connected"
    }


@pytest.mark.parametrize(
    ("row", "expected_command"),
    [
        (0, 0x06),
        (1, 0x08),
        (2, 0x0A),
    ],
)
def test_open_servo_sends_arm_command(row, expected_command):
    reset_servo_state()
    publisher = RecordingControlPublisher()
    client = make_client(publisher)

    response = client.post("/controls/api/servo/open", json={"row": row})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert publisher.commands == [expected_command]
    assert state["servos"][row]["status"] == "OPEN"


@pytest.mark.parametrize(
    ("row", "expected_command"),
    [
        (0, 0x07),
        (1, 0x09),
        (2, 0x0B),
    ],
)
def test_close_servo_sends_abort_command(row, expected_command):
    reset_servo_state()
    state["servos"][row]["status"] = "OPEN"
    publisher = RecordingControlPublisher()
    client = make_client(publisher)

    response = client.post("/controls/api/servo/close", json={"row": row})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert publisher.commands == [expected_command]
    assert state["servos"][row]["status"] == "CLOSED"


def test_open_servo_skips_duplicate_command():
    reset_servo_state()
    state["servos"][0]["status"] = "OPEN"
    publisher = RecordingControlPublisher()
    client = make_client(publisher)

    response = client.post("/controls/api/servo/open", json={"row": 0})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert publisher.commands == []
    assert state["event_log"] == []


def test_close_servo_skips_duplicate_command():
    reset_servo_state()
    publisher = RecordingControlPublisher()
    client = make_client(publisher)

    response = client.post("/controls/api/servo/close", json={"row": 0})

    assert response.status_code == 200
    assert response.json() == {"ok": True}
    assert publisher.commands == []
    assert state["event_log"] == []


@pytest.mark.parametrize("route", [
    "/controls/api/servo/open",
    "/controls/api/servo/close",
])
@pytest.mark.parametrize("row", [-1, 3])
def test_servo_route_rejects_invalid_row(route, row):
    reset_servo_state()
    client = make_client(RecordingControlPublisher())

    response = client.post(route, json={"row": row})

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid servo row"}


def test_servo_route_does_not_update_state_when_mqtt_is_disabled():
    reset_servo_state()
    client = make_client(DisabledControlPublisher())

    response = client.post("/controls/api/servo/open", json={"row": 0})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "MQTT control publisher is not connected"
    }
    assert state["servos"][0]["status"] == "CLOSED"


@pytest.mark.parametrize(
    ("error_cls", "message", "expected_status"),
    [
        (CommandTimeout, "no response from board after 3s", 504),
        (CommandRejected, "servo jammed", 502),
    ],
)
def test_servo_failure_logs_error_and_keeps_state(
    error_cls, message, expected_status
):
    reset_servo_state()
    client = make_client(FailingControlPublisher(error_cls, message))

    response = client.post("/controls/api/servo/open", json={"row": 0})

    assert response.status_code == expected_status
    assert response.json() == {"detail": message}
    assert state["servos"][0]["status"] == "CLOSED"
    assert len(state["event_log"]) == 1
    assert state["event_log"][0].endswith(
        f"Command 0x06 (id 7) failed: {message}"
    )


def test_ping_board_blinks_led_three_times(monkeypatch):
    async def skip_sleep(delay):
        return None

    reset_servo_state()
    monkeypatch.setattr(control.asyncio, "sleep", skip_sleep)
    publisher = RecordingControlPublisher()
    client = make_client(publisher)

    response = client.post("/controls/api/ping")

    assert response.status_code == 200
    assert response.json() == {"ok": True, "message": "Ping sent"}
    assert publisher.commands == [0x0F, 0x0E, 0x0F, 0x0E, 0x0F, 0x0E]
    assert len(state["event_log"]) == 1
    assert state["event_log"][0].endswith("Ping blink sent to board")


def test_ping_board_returns_unavailable_when_mqtt_is_disabled(monkeypatch):
    async def skip_sleep(delay):
        return None

    reset_servo_state()
    monkeypatch.setattr(control.asyncio, "sleep", skip_sleep)
    client = make_client(DisabledControlPublisher())

    response = client.post("/controls/api/ping")

    assert response.status_code == 503
    assert response.json() == {
        "detail": "MQTT control publisher is not connected"
    }
    assert state["event_log"] == []
