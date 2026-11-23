"""Exercise the reference transports against real WebSocket and serial peers."""

from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import pytest
from websockets.asyncio.server import ServerConnection, serve

from mesh import connections
from mesh.messages import MeshMsgCan, MeshMsgCanAck, MeshMsgDo, MeshMsgMeta

MESSAGES = Path(__file__).resolve().parents[3] / "tests"
CAN = MeshMsgCan(
    meta=MeshMsgMeta(version=1, node_from="client", node_to="server", hops=[]),
    payload=MeshMsgCan.Payload(),
)
CAN_ACK = MeshMsgCanAck(
    meta=MeshMsgMeta(version=1, node_from="server", node_to="client", hops=[]),
    payload=MeshMsgCanAck.Payload(can=[]),
)


@pytest.mark.parametrize(
    "transport", [connections.WebSocketConnection, connections.UsbCdcAcmConnection]
)
def test_transport_inherits_directly_from_base_connection(
    transport: type[connections.BaseConnection],
) -> None:
    """Require the public base to be the transport's immediate parent.

    :param transport: Concrete transport class to inspect.
    """
    assert transport.__bases__ == (connections.BaseConnection,)


def test_websocket_exchanges_requests_in_both_directions() -> None:
    """Route each reply to its waiting sender while exposing peer requests."""

    async def exchange(
        incoming: connections.BaseConnection, outgoing: MeshMsgCan
    ) -> None:
        """Send a request and acknowledge the peer's simultaneous request.

        :param incoming: Open connection on this side of the socket.
        :param outgoing: Request originating from this side.
        """
        reply = asyncio.create_task(incoming.send(outgoing))
        request = await incoming.receive()
        assert isinstance(request, MeshMsgCan)
        ack = MeshMsgCanAck(meta=outgoing.meta, payload=MeshMsgCanAck.Payload(can=[]))
        await incoming.send_faf(ack)
        assert await reply == MeshMsgCanAck(
            meta=request.meta, payload=MeshMsgCanAck.Payload(can=[])
        )

    async def accept(socket: ServerConnection) -> None:
        """Wrap an accepted WebSocket and exchange mesh messages.

        :param socket: Server side of the WebSocket.
        """
        connection = connections.WebSocketConnection(socket)
        await connection.connect()
        try:
            await exchange(
                connection, MeshMsgCan(meta=CAN_ACK.meta, payload=CAN.payload)
            )
        finally:
            await connection.disconnect()

    async def run() -> None:
        """Run a Mesh exchange over an ephemeral local WebSocket listener."""
        async with serve(accept, "127.0.0.1", 0) as server:
            url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            client = connections.WebSocketConnection(url)
            assert await client.discover() == [client]
            await client.connect()
            try:
                await exchange(client, CAN)
            finally:
                await client.disconnect()

    asyncio.run(asyncio.wait_for(run(), 5))


def test_websocket_timeout_closes_the_session_before_another_request() -> None:
    """Require a fresh session after a timed-out request."""

    async def accept(socket: ServerConnection) -> None:
        """Read one request and leave it unacknowledged.

        :param socket: Server side of the WebSocket.
        """
        assert json.loads(await socket.recv()) == CAN.model_dump()
        await socket.wait_closed()

    async def run() -> None:
        """Verify the timed-out requester cannot reuse the old socket."""
        async with serve(accept, "127.0.0.1", 0) as server:
            url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            connection = connections.WebSocketConnection(url, response_timeout=0.05)
            await connection.connect()
            try:
                with pytest.raises(TimeoutError):
                    await connection.send(CAN)
                with pytest.raises(ConnectionError):
                    await connection.send(CAN)
            finally:
                await connection.disconnect()

    asyncio.run(asyncio.wait_for(run(), 5))


def test_websocket_forwards_unmatched_acknowledgements() -> None:
    """Keep acknowledgements for a different destination out of the pending send."""

    async def accept(socket: ServerConnection) -> None:
        """Send an unrelated reply followed by the expected reply.

        :param socket: Server side of the WebSocket.
        """
        await socket.recv()
        other = CAN_ACK.model_copy(
            update={"meta": CAN_ACK.meta.model_copy(update={"node_to": "other"})}
        )
        await socket.send(other.model_dump_json())
        await socket.send(CAN_ACK.model_dump_json())

    async def run() -> None:
        """Read the two replies through the distinct connection methods."""
        async with serve(accept, "127.0.0.1", 0) as server:
            url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            connection = await connections.WebSocketConnection(url).connect()
            try:
                assert await connection.send(CAN) == CAN_ACK
                assert (await connection.receive()).meta.node_to == "other"
                with pytest.raises(ConnectionError):
                    await connection.receive()
            finally:
                await connection.disconnect()

    asyncio.run(asyncio.wait_for(run(), 5))


@pytest.mark.skipif(os.name != "posix", reason="requires a POSIX pseudo-terminal")
def test_usb_serial_preserves_split_and_consecutive_json_frames() -> None:
    """Decode typed messages across reads and emit newline-delimited UTF-8."""
    import pty

    async def run(port: str, peer_fd: int) -> None:
        """Exchange mesh messages with the other side of a pseudo-terminal.

        :param port: Host-side serial device path.
        :param peer_fd: Descriptor used by the simulated device.
        """
        connection = await connections.UsbCdcAcmConnection(port).connect()
        try:
            pending = asyncio.create_task(connection.send(CAN))
            outbound = bytearray()
            while not outbound.endswith(b"\n"):
                try:
                    outbound.extend(os.read(peer_fd, 4096))
                except BlockingIOError:
                    await asyncio.sleep(0.01)
            assert json.loads(outbound) == CAN.model_dump()

            lines = (MESSAGES / "messages-valid.jsonl").read_bytes().splitlines()
            do_frame = next(line for line in lines if json.loads(line)["msg"] == "do")
            ack = CAN_ACK.model_dump_json().encode()
            os.write(peer_fd, ack[:10])
            await asyncio.sleep(0.05)
            assert not pending.done()
            os.write(peer_fd, ack[10:] + b"\r\n" + do_frame + b"\n")
            assert await pending == CAN_ACK
            message = await connection.receive()
            assert isinstance(message, MeshMsgDo)
            assert message.payload.input == json.loads(do_frame)["payload"]["input"]
        finally:
            await connection.disconnect()

    master, slave = pty.openpty()
    try:
        os.set_blocking(master, False)
        asyncio.run(asyncio.wait_for(run(os.ttyname(slave), master), 5))
    finally:
        os.close(master)
        os.close(slave)


def test_websocket_disconnect_wakes_all_receivers() -> None:
    """Unblock every pending receive when the client disconnects."""

    async def accept(socket: ServerConnection) -> None:
        """Keep the server side open until the client closes it.

        :param socket: Server side of the WebSocket.
        """
        await socket.wait_closed()

    async def run() -> None:
        """Disconnect while two tasks are awaiting incoming messages."""
        async with serve(accept, "127.0.0.1", 0) as server:
            url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            connection = await connections.WebSocketConnection(url).connect()
            first = asyncio.create_task(connection.receive())
            second = asyncio.create_task(connection.receive())
            await asyncio.sleep(0)
            await connection.disconnect()
            results = await asyncio.gather(first, second, return_exceptions=True)
            assert all(isinstance(result, ConnectionError) for result in results)

    asyncio.run(asyncio.wait_for(run(), 5))


def test_websocket_rejects_invalid_message_payload() -> None:
    """Validate payload fields using the concrete message model."""

    async def accept(socket: ServerConnection) -> None:
        """Send a message with a missing required field.

        :param socket: Server side of the WebSocket.
        """
        frame = CAN_ACK.model_dump()
        del frame["payload"]["can"]
        await socket.send(json.dumps(frame))
        await socket.wait_closed()

    async def run() -> None:
        """Read the invalid frame through the public connection API."""
        async with serve(accept, "127.0.0.1", 0) as server:
            url = f"ws://127.0.0.1:{server.sockets[0].getsockname()[1]}"
            connection = await connections.WebSocketConnection(url).connect()
            try:
                with pytest.raises(ConnectionError):
                    await connection.receive()
            finally:
                await connection.disconnect()

    asyncio.run(asyncio.wait_for(run(), 5))
