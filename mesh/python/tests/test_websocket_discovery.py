"""Exercise LAN discovery against real WebSocket listeners."""

import asyncio
from http import HTTPStatus

import pytest
from websockets.asyncio.server import ServerConnection, serve
from websockets.http11 import Request, Response

from mesh.connections import WebSocketConnection
from mesh.messages import MeshMsgCan, MeshMsgCanAck, MeshMsgHello, MeshMsgHelloAck, MeshMsgMeta
from mesh.types import Greeting

LOCAL = Greeting(node_id="scanner", name="Scanner", version=1)
PEER = Greeting(node_id="peer", name="Peer", version=1)
LOOPBACK = "127.0.0.1/32"


def test_discovery_exchanges_hello_and_returns_a_live_connection() -> None:
    """Discover an unknown node ID and reuse the verified session for requests."""

    async def accept(socket: ServerConnection) -> None:
        """Answer the discovery hello and then a capability request."""
        connection = await WebSocketConnection(socket).connect()
        try:
            request = await connection.receive()
            assert isinstance(request, MeshMsgHello)
            assert request.meta == MeshMsgMeta(
                version=1, node_from="scanner", node_to="", hops=["scanner"]
            )
            assert request.payload.greeting == LOCAL
            reply_meta = MeshMsgMeta(
                version=1, node_from="peer", node_to="scanner", hops=["peer"]
            )
            await connection.send_faf(MeshMsgHelloAck(
                meta=reply_meta, payload=MeshMsgHelloAck.Payload(greeting=PEER)
            ))
            assert isinstance(await connection.receive(), MeshMsgCan)
            await connection.send_faf(MeshMsgCanAck(
                meta=reply_meta, payload=MeshMsgCanAck.Payload(can=[])
            ))
        finally:
            await connection.disconnect()

    async def run() -> None:
        """Start a peer on an ephemeral scan port."""
        async with serve(accept, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            peers = await WebSocketConnection().discover(
                LOCAL, network=LOOPBACK, port=port
            )
            assert len(peers) == 1
            peer = peers[0]
            try:
                assert peer.endpoint == f"ws://127.0.0.1:{port}/"
                assert peer.peer_greeting == PEER
                reply = await peer.send(MeshMsgCan(
                    meta=MeshMsgMeta(
                        version=1, node_from="scanner", node_to="peer", hops=["scanner"]
                    ),
                    payload=MeshMsgCan.Payload(),
                ))
                assert isinstance(reply, MeshMsgCanAck)
            finally:
                await peer.disconnect()

    asyncio.run(asyncio.wait_for(run(), 5))


@pytest.mark.parametrize(
    ("node_from", "node_to", "greeting"),
    [("peer", "scanner", LOCAL), ("scanner", "scanner", LOCAL),
     ("peer", "different-node", PEER), ("peer", "scanner", None)],
)
def test_discovery_closes_unverified_peers(
    node_from: str, node_to: str, greeting: Greeting | None
) -> None:
    """Discard invalid acknowledgements, self-discovery, and silent peers."""
    closed = False

    async def accept(socket: ServerConnection) -> None:
        """Wait for hello and optionally send an invalid reply."""
        nonlocal closed
        await socket.recv()
        if greeting is not None:
            await socket.send(MeshMsgHelloAck(
                meta=MeshMsgMeta(version=1, node_from=node_from, node_to=node_to, hops=[]),
                payload=MeshMsgHelloAck.Payload(greeting=greeting),
            ).model_dump_json())
        await socket.wait_closed()
        closed = True

    async def run() -> None:
        """Reject the candidate and check that its socket closes."""
        async with serve(accept, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            assert await WebSocketConnection().discover(
                LOCAL, network=LOOPBACK, port=port, probe_timeout=0.2
            ) == []

    asyncio.run(asyncio.wait_for(run(), 5))
    assert closed


def test_discovery_does_not_follow_redirects_to_other_ports() -> None:
    """Keep discovery traffic on the selected WebSocket port."""

    async def run() -> None:
        """Redirect the discovery handshake to a separate WebSocket server."""
        redirects = 0

        async def accept(socket: ServerConnection) -> None:
            """Count any successful upgrade at the redirect destination."""
            nonlocal redirects
            redirects += 1

        async with serve(accept, "127.0.0.1", 0) as other:
            other_port = other.sockets[0].getsockname()[1]

            def redirect(socket: ServerConnection, request: Request) -> Response:
                """Return a redirect off the scanned port."""
                response = socket.respond(HTTPStatus.TEMPORARY_REDIRECT, "Moved")
                response.headers["Location"] = f"ws://127.0.0.1:{other_port}/"
                return response

            async with serve(accept, "127.0.0.1", 0, process_request=redirect) as server:
                port = server.sockets[0].getsockname()[1]
                assert await WebSocketConnection().discover(
                    LOCAL, network=LOOPBACK, port=port
                ) == []
        assert redirects == 0

    asyncio.run(asyncio.wait_for(run(), 5))
