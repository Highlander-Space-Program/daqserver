from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.web.routes.control import router


class FakeControlPublisher:
    def get_breakwire_status(self):
        return {"status": "broken"}


class DisabledControlPublisher(FakeControlPublisher):
    def send_command(self, command: int):
        return False


def test_breakwire_route_returns_current_status():
    app = FastAPI()
    app.state.control_publisher = FakeControlPublisher()
    app.include_router(router)

    response = TestClient(app).get("/controls/api/breakwire")

    assert response.status_code == 200
    assert response.json() == {"status": "broken"}


def test_command_route_returns_unavailable_when_mqtt_is_disabled():
    app = FastAPI()
    app.state.control_publisher = DisabledControlPublisher()
    app.include_router(router)

    response = TestClient(app).post("/controls/api/command", json={"command": 1})

    assert response.status_code == 503
    assert response.json() == {
        "detail": "MQTT control publisher is not connected"
    }
