"""Tests for the standalone mesh worker websocket entrypoint."""

import threading
from collections.abc import Iterator

import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from lange.contracts.mesh import MeshMessage
from lange.contracts.relay import MeshRelayRequest, MeshRelayResponse

from mesh_service import state
from mesh_service.endpoints.workers import workers_router
from mesh_service.router import MeshRouter


@pytest.fixture(autouse=True)
def mesh_worker_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset mesh worker settings and router state around each test."""
    monkeypatch.setenv("MESH_BASE_DOMAIN", "mesh.lange-labs.com")
    monkeypatch.delenv("MESH_WORKER_SECRET", raising=False)
    state.MESH_ROUTER = MeshRouter()
    yield
    state.MESH_ROUTER = MeshRouter()


def test_relay_request_sends_worker_json_object_frame() -> None:
    """Assert queued relay requests reach workers as JSON object frames."""
    app = FastAPI()
    app.include_router(workers_router, prefix="/v1")

    @app.get("/status")
    async def relay_status() -> Response:
        """Relay one test request through the registered worker."""
        relay_response = await state.MESH_ROUTER.relay_rest(
            "demo",
            MeshRelayRequest(method="GET", path="/status"),
        )
        return Response(
            content=relay_response.body or b"",
            status_code=relay_response.status,
        )

    registration = {"name": "demo", "requestTimeoutSeconds": 5.0}
    response_holder: dict[str, object] = {}

    with TestClient(app) as client:
        with client.websocket_connect("/v1/workers/entrypoint") as websocket:
            websocket.send_json(
                MeshMessage(status="hello", data=registration).model_dump(mode="json")
            )
            websocket.receive_json()
            websocket.send_json(
                MeshMessage(status="ready", data=None).model_dump(mode="json")
            )

            def request_relay() -> None:
                """Send one relay request while the worker websocket is open."""
                response_holder["response"] = client.get("/status")

            relay_thread = threading.Thread(target=request_relay)
            relay_thread.start()

            worker_payload = websocket.receive_json()
            assert isinstance(worker_payload, dict)
            request_message = MeshMessage.model_validate(worker_payload)
            assert request_message.status == "request"
            assert isinstance(request_message.data, MeshRelayRequest)
            assert request_message.data.method == "GET"

            websocket.send_json(
                MeshMessage(
                    id=request_message.id,
                    status="response",
                    data=MeshRelayResponse(status=200, body="ok"),
                ).model_dump(mode="json")
            )
            relay_thread.join(timeout=2)

    assert not relay_thread.is_alive()
    response = response_holder["response"]
    assert response.status_code == 200
    assert response.content == b"ok"
