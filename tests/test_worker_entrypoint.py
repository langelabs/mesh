"""Tests for the standalone mesh worker websocket entrypoint."""

import asyncio
import threading
from collections.abc import Iterator
from typing import Any

import httpx
import pytest
from fastapi import FastAPI, Response
from fastapi.testclient import TestClient
from lange.contracts.mesh import MeshMessage
from lange.contracts.relay import MeshRelayRequest, MeshRelayResponse
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocket

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


def _register_ready_worker(
    websocket: WebSocketTestSession,
    *,
    name: str = "demo",
    timeout: float = 5.0,
) -> None:
    """Register a websocket worker and wait until ready is processed.

    :param websocket: Worker websocket test session.
    :param name: Relay worker name to register.
    :param timeout: Relay request timeout to register.
    """
    registration = {"name": name, "timeout": timeout}
    websocket.send_json(
        MeshMessage(status="hello", type="manage", data=registration).model_dump(mode="json")
    )
    websocket.receive_json()
    websocket.send_json(
        MeshMessage(status="ready", type="manage", data=None).model_dump(mode="json")
    )
    websocket.send_json(
        MeshMessage(status="ping", type="manage", data=None).model_dump(mode="json")
    )
    websocket.receive_json()


def test_worker_entrypoint_stores_direct_peer_ip_address() -> None:
    """Assert registered workers store the websocket peer address."""
    app = FastAPI()
    app.include_router(workers_router, prefix="/v1")

    with TestClient(app) as client:
        with client.websocket_connect(
            "/v1/workers/entrypoint",
            headers={"X-Forwarded-For": "203.0.113.10"},
        ) as websocket:
            _register_ready_worker(websocket)

            worker = state.MESH_ROUTER.workers["demo"][0]
            assert worker.ip_address is not None
            assert worker.ip_address != "203.0.113.10"


def test_get_workers_returns_registered_worker_ip_address() -> None:
    """Assert the workers view includes the stored websocket peer address."""
    app = FastAPI()
    app.include_router(workers_router, prefix="/v1")

    with TestClient(app) as client:
        with client.websocket_connect("/v1/workers/entrypoint") as websocket:
            _register_ready_worker(websocket)
            worker = state.MESH_ROUTER.workers["demo"][0]

            response = client.get("/v1/workers")

            assert response.status_code == 200
            assert response.json() == {
                "workers": [
                    {
                        "name": "demo",
                        "ip_address": worker.ip_address,
                        "timeout": 5.0,
                        "status": "ready",
                    }
                ]
            }


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

    registration = {"name": "demo", "timeout": 5.0}
    response_holder: dict[str, object] = {}

    with TestClient(app) as client:
        with client.websocket_connect("/v1/workers/entrypoint") as websocket:
            websocket.send_json(
                MeshMessage(status="hello", type="manage", data=registration).model_dump(mode="json")
            )
            websocket.receive_json()
            websocket.send_json(
                MeshMessage(status="ready", type="manage", data=None).model_dump(mode="json")
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
                    type="relay",
                    data=MeshRelayResponse(status=200, body="ok"),
                ).model_dump(mode="json")
            )
            relay_thread.join(timeout=2)

    assert not relay_thread.is_alive()
    response = response_holder["response"]
    assert response.status_code == 200
    assert response.content == b"ok"


def test_worker_entrypoint_serializes_control_and_relay_frames(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assert one writer task sends both control and relay websocket frames.

    :param monkeypatch: Pytest patch helper used to observe websocket sends.
    """
    app = FastAPI()
    app.include_router(workers_router, prefix="/v1")
    response_holder: dict[str, httpx.Response] = {}
    writer_tasks: set[asyncio.Task[Any]] = set()
    original_send_json = WebSocket.send_json

    async def record_send_task(
        websocket: WebSocket,
        data: Any,
        mode: str = "text",
    ) -> None:
        """Record the current sender task before forwarding one JSON frame.

        :param websocket: Server websocket sending the frame.
        :param data: JSON-compatible frame payload.
        :param mode: Starlette websocket frame mode.
        """
        writer_task = asyncio.current_task()
        assert writer_task is not None
        writer_tasks.add(writer_task)
        await original_send_json(websocket, data, mode=mode)

    monkeypatch.setattr(WebSocket, "send_json", record_send_task)

    @app.get("/status")
    async def relay_status() -> Response:
        """Relay one request while the registered worker is connected."""
        relay_response = await state.MESH_ROUTER.relay_rest(
            "demo",
            MeshRelayRequest(method="GET", path="/status"),
        )
        return Response(status_code=relay_response.status)

    with TestClient(app) as client:
        with client.websocket_connect("/v1/workers/entrypoint") as websocket:
            _register_ready_worker(websocket)

            def request_relay() -> None:
                """Send one relay request from a parallel HTTP client thread."""
                response_holder["response"] = client.get("/status")

            relay_thread = threading.Thread(target=request_relay)
            relay_thread.start()
            request_message = MeshMessage.model_validate(websocket.receive_json())
            websocket.send_json(
                MeshMessage(
                    id=request_message.id,
                    status="response",
                    type="relay",
                    data=MeshRelayResponse(status=204),
                ).model_dump(mode="json")
            )
            relay_thread.join(timeout=2)

    assert not relay_thread.is_alive()
    assert response_holder["response"].status_code == 204
    assert len(writer_tasks) == 1
