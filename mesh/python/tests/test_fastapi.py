"""Exercise the Mesh router in a host FastAPI app."""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI, WebSocketDisconnect
from fastapi.testclient import TestClient

from mesh import connections
from mesh.connections.__base import MAX_MESSAGE_BYTES
from mesh.connections.fastapi import create_mesh_router
from mesh.connections.fastapi._router import MeshAPIRouter, get_mesh_router
from mesh.messages import (
    MeshMsgCan,
    MeshMsgCanAck,
    MeshMsgDo,
    MeshMsgDoAck,
    MeshMsgHello,
    MeshMsgHelloAck,
    MeshMsgMeta,
)
from mesh.router import MeshRouter
from mesh.types import Greeting


@pytest.fixture
def host() -> Iterator[tuple[TestClient, MeshRouter]]:
    """Mount a Mesh node in an existing FastAPI app.

    :yields: The client and mounted node.
    """
    app = FastAPI()
    node = MeshRouter()
    app.include_router(connections.create_mesh_router(node))
    with TestClient(app) as client:
        yield client, node


def test_well_known_returns_the_node_greeting(
    host: tuple[TestClient, MeshRouter],
) -> None:
    """Return the mounted node's identity as a Greeting.

    :param host: Client and node mounted in the host app.
    """
    client, node = host
    response = client.get("/.well-known/mesh")

    assert response.status_code == 200
    assert Greeting.model_validate(response.json()) == Greeting(
        node_id=node._id, name=node._name, version=node._version
    )


def test_both_endpoints_use_the_injected_router() -> None:
    """Override the router dependency for both HTTP and WebSocket requests."""
    app = FastAPI()
    app.include_router(create_mesh_router(MeshRouter()))
    injected = MeshRouter()
    injected_router = create_mesh_router(injected)
    node_id = injected.get_greeting().node_id

    async def override_router() -> MeshAPIRouter:
        """Return the router selected by the host app for this test.

        :returns: Router bound to the replacement Mesh node.
        """
        return injected_router

    app.dependency_overrides[get_mesh_router] = override_router
    request = MeshMsgCan(
        meta=MeshMsgMeta(version=0, node_from="peer", node_to=node_id, hops=["peer"]),
        payload=MeshMsgCan.Payload(),
    )

    with TestClient(app) as client:
        assert client.get("/.well-known/mesh").json()["node_id"] == node_id
        with client.websocket_connect("/mesh") as socket:
            socket.send_text(request.model_dump_json())
            reply = MeshMsgCanAck.model_validate_json(socket.receive_text())
            assert reply.meta.node_from == node_id


def test_websocket_dispatches_mesh_messages(
    host: tuple[TestClient, MeshRouter],
) -> None:
    """Exchange typed Mesh acknowledgements on an open WebSocket.

    :param host: Client and node mounted in the host app.
    """
    client, node = host
    peer = Greeting(node_id="peer", name="Peer", version=0)
    hello = MeshMsgHello(
        meta=MeshMsgMeta(
            version=0, node_from=peer.node_id, node_to="", hops=[peer.node_id]
        ),
        payload=MeshMsgHello.Payload(greeting=peer),
    )

    @node.meshed
    async def echo(value: str) -> str:
        """Return the provided value.

        :param value: Value received from the remote node.
        :returns: The provided value.
        """
        return value

    with client.websocket_connect("/mesh") as socket:
        socket.send_text(hello.model_dump_json())
        reply = MeshMsgHelloAck.model_validate_json(socket.receive_text())
        assert reply.payload.greeting == Greeting.model_validate(
            client.get("/.well-known/mesh").json()
        )
        assert reply.meta.node_to == peer.node_id
        assert node._friends[peer.node_id].name == peer.name

        request = MeshMsgDo(
            meta=hello.meta.model_copy(update={"node_to": reply.meta.node_from}),
            payload=MeshMsgDo.Payload(
                id=f"{echo.__module__}.{echo.__qualname__}", input=["hello"]
            ),
        )
        socket.send_text(request.model_dump_json())
        result = MeshMsgDoAck.model_validate_json(socket.receive_text())
        assert result.payload.outputs == ["hello"]


@pytest.mark.parametrize(
    ("frame", "code"),
    [(b"{}", 1003), ("invalid JSON", 1007), ("é" * (MAX_MESSAGE_BYTES // 2 + 1), 1009)],
    ids=["binary", "invalid", "oversized"],
)
def test_websocket_closes_on_invalid_frames(
    host: tuple[TestClient, MeshRouter], frame: str | bytes, code: int
) -> None:
    """Close an invalid WebSocket session with the matching protocol code.

    :param host: Client and node mounted in the host app.
    :param frame: Invalid binary, JSON, or oversized frame.
    :param code: Expected WebSocket close code.
    """
    client, _ = host
    with client.websocket_connect("/mesh") as socket:
        if isinstance(frame, bytes):
            socket.send_bytes(frame)
        else:
            socket.send_text(frame)
        with pytest.raises(WebSocketDisconnect) as closed:
            socket.receive_text()
        assert closed.value.code == code
