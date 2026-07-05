"""Integration tests for the standalone mesh relay service."""

import base64
import uuid
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from lange.contracts.mesh import MeshMessage
from lange.contracts.relay import MeshRelayRequest, MeshRelayResponse
from starlette.websockets import WebSocketDisconnect

from mesh_service import main as mesh_main
from mesh_service import state
from mesh_service.router import MeshRouter


def test_relay_handler_is_not_defined_in_main_module() -> None:
    """Assert the public relay handler lives in the relay endpoint package."""
    assert not hasattr(mesh_main, "relay_mesh_request")


class _FakeRouter:
    """Test double that records relay requests sent through the mesh app."""

    def __init__(
        self,
        *,
        response: MeshRelayResponse | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Initialize the fake router result behavior.

        :param response: Relay response to return from ``relay_rest``.
        :param error: Error to raise from ``relay_rest``.
        """
        self.response = response or MeshRelayResponse(status=200, body="ok")
        self.error = error
        self.calls: list[tuple[str, MeshRelayRequest]] = []

    async def relay_rest(
        self,
        name: str,
        request: MeshRelayRequest,
    ) -> MeshRelayResponse:
        """Record and resolve one relay request.

        :param name: Relay worker name selected from the public host.
        :param request: Request payload sent to the relay worker.
        :returns: Configured relay response.
        :raises BaseException: Configured relay error.
        """
        self.calls.append((name, request))
        if self.error is not None:
            raise self.error
        return self.response


@pytest.fixture(autouse=True)
def mesh_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset mesh settings and router state around each app test."""
    monkeypatch.setenv("MESH_BASE_DOMAIN", "mesh.lange-labs.com")
    monkeypatch.delenv("MESH_WORKER_SECRET", raising=False)
    state.MESH_ROUTER = MeshRouter()
    yield
    state.MESH_ROUTER = MeshRouter()


def test_health_returns_ok() -> None:
    """Assert the bare mesh service health endpoint is available."""
    with TestClient(mesh_main.app) as client:
        response = client.get(
            "/health",
            headers={"host": "mesh.lange-labs.com"},
        )

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_old_root_entrypoint_is_not_mounted() -> None:
    """Assert workers must use the versioned entrypoint route."""
    with TestClient(mesh_main.app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/entrypoint"):
                pass


def test_worker_entrypoint_allows_connection_without_secret() -> None:
    """Assert worker auth is disabled when no mesh worker secret is configured."""
    registration = {"name": "demo", "timeout": 5.0}
    with TestClient(mesh_main.app) as client:
        with client.websocket_connect("/v1/workers/entrypoint") as websocket:
            websocket.send_json(
                MeshMessage(status="hello", type="manage", data=registration).model_dump(mode="json")
            )
            hello_response = websocket.receive_json()
            websocket.send_json(
                MeshMessage(status="ready", type="manage", data=None).model_dump(mode="json")
            )
            websocket.send_json(
                MeshMessage(status="ping", type="manage", data=None).model_dump(mode="json")
            )
            ready_response = websocket.receive_json()

            assert hello_response["status"] == "hello"
            assert hello_response["data"]["remote_relay_address"] == "https://demo.mesh.lange-labs.com/"
            assert hello_response["data"]["type"] == "REST"
            assert ready_response["status"] == "ready"
            assert "demo" in state.MESH_ROUTER.workers

    assert state.MESH_ROUTER.workers == {}


def test_worker_entrypoint_requires_bearer_auth_when_secret_is_configured(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assert configured worker secrets reject missing or invalid bearer headers."""
    monkeypatch.setenv("MESH_WORKER_SECRET", "secret-token")

    with TestClient(mesh_main.app) as client:
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/v1/workers/entrypoint"):
                pass
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect(
                "/v1/workers/entrypoint",
                headers={"Authorization": "Bearer wrong-token"},
            ):
                pass


def test_worker_entrypoint_accepts_valid_bearer_auth(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Assert configured worker secrets accept matching bearer headers."""
    monkeypatch.setenv("MESH_WORKER_SECRET", "secret-token")

    with TestClient(mesh_main.app) as client:
        with client.websocket_connect(
            "/v1/workers/entrypoint",
            headers={"Authorization": "Bearer secret-token"},
        ) as websocket:
            websocket.send_json(
                MeshMessage(status="ping", type="manage", data=None).model_dump(mode="json")
            )
            response = websocket.receive_json()

    assert response["status"] == "ready"


def test_named_get_routes_through_in_process_mesh_router() -> None:
    """Assert public relay GET requests are sent to the local mesh router."""
    router = _FakeRouter(
        response=MeshRelayResponse(
            status=202,
            headers={"x-relay": "yes"},
            body=base64.b64encode(b"relay response").decode("ascii"),
            body_encoding="base64",
        )
    )
    state.MESH_ROUTER = router

    with TestClient(mesh_main.app) as client:
        response = client.get(
            "/status?x=1&x=2",
            headers={"host": "demo.mesh.lange-labs.com"},
        )

    assert response.status_code == 202
    assert response.content == b"relay response"
    assert response.headers["x-relay"] == "yes"
    assert router.calls[0][0] == "demo"
    assert router.calls[0][1].method == "GET"
    assert router.calls[0][1].path == "/status"
    assert router.calls[0][1].query_params == {"x": ["1", "2"]}
    assert router.calls[0][1].body is None


def test_named_post_routes_body_through_in_process_mesh_router() -> None:
    """Assert public relay POST requests preserve body bytes and content headers."""
    router = _FakeRouter(response=MeshRelayResponse(status=204))
    state.MESH_ROUTER = router

    with TestClient(mesh_main.app) as client:
        response = client.post(
            "/submit",
            headers={
                "host": "demo.mesh.lange-labs.com",
                "content-type": "application/json",
            },
            content=b'{"ok": true}',
        )

    assert response.status_code == 204
    assert router.calls[0][1].method == "POST"
    assert router.calls[0][1].path == "/submit"
    assert router.calls[0][1].headers["content-type"] == "application/json"
    assert router.calls[0][1].body == base64.b64encode(b'{"ok": true}').decode("ascii")
    assert router.calls[0][1].body_encoding == "base64"


def test_no_registered_worker_returns_service_unavailable() -> None:
    """Assert missing relay workers produce a 503 response."""
    state.MESH_ROUTER = _FakeRouter(error=RuntimeError("No workers registered for name demo"))

    with TestClient(mesh_main.app) as client:
        response = client.get(
            "/status",
            headers={"host": "demo.mesh.lange-labs.com"},
        )

    assert response.status_code == 503
    assert response.json()["detail"] == "No relay worker is connected for this name."


def test_worker_timeout_returns_gateway_timeout() -> None:
    """Assert worker relay timeouts produce a 504 response."""
    state.MESH_ROUTER = _FakeRouter(error=TimeoutError())

    with TestClient(mesh_main.app) as client:
        response = client.get(
            "/status",
            headers={"host": "demo.mesh.lange-labs.com"},
        )

    assert response.status_code == 504
    assert response.json()["detail"] == "Relay worker did not return a response in time."


def test_invalid_host_returns_not_found() -> None:
    """Assert non-mesh hosts are rejected before reaching the mesh router."""
    state.MESH_ROUTER = _FakeRouter(error=AssertionError("router should not be called"))

    with TestClient(mesh_main.app) as client:
        response = client.get(
            "/status",
            headers={"host": "lange-labs.com"},
        )

    assert response.status_code == 404


def test_head_response_does_not_include_body() -> None:
    """Assert HEAD relay responses strip the response body."""
    router = _FakeRouter(
        response=MeshRelayResponse(
            status=200,
            body=base64.b64encode(b"hidden").decode("ascii"),
            body_encoding="base64",
        )
    )
    state.MESH_ROUTER = router

    with TestClient(mesh_main.app) as client:
        response = client.head(
            f"/status?request_id={uuid.uuid4()}",
            headers={"host": "demo.mesh.lange-labs.com"},
        )

    assert response.status_code == 200
    assert response.content == b""
