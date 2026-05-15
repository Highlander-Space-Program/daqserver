from fastapi import FastAPI
from fastapi.testclient import TestClient

from server.web.routes.control import router


class FakeControlPublisher:
    def get_breakwire_status(self):
        return {"status": "broken"}


def test_breakwire_route_returns_current_status():
    app = FastAPI()
    app.state.control_publisher = FakeControlPublisher()
    app.include_router(router)

    response = TestClient(app).get("/controls/api/breakwire")

    assert response.status_code == 200
    assert response.json() == {"status": "broken"}
