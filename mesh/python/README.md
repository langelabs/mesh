# Mesh Python reference implementation

The `mesh.connections` package provides two asyncio implementations of
`BaseConnection`. Call `connect()` before transferring messages and
`disconnect()` when finished. Use the connection methods on the same event
loop.

| Connection | Endpoint | Wire format |
| --- | --- | --- |
| `WebSocketConnection("wss://host/path")` | A configured `ws://` or `wss://` URL. A server can pass an accepted `websockets` `ServerConnection` instead. | One JSON envelope per WebSocket text message. |
| `UsbCdcAcmConnection("/dev/ttyACM0")` | An OS serial path or COM port. The default is 115200 baud, 8 data bits, no parity, and one stop bit. | One UTF-8 JSON envelope per line. Sends LF and accepts LF or CRLF. |

Both transports limit the JSON body to 1 MiB. On a WebSocket server, set
`max_size=1048576` on `websockets.asyncio.server.serve` to enforce the same
limit during WebSocket message assembly.

`UsbCdcAcmConnection.discover()` returns unopened local USB serial candidates
with vendor and product IDs. `WebSocketConnection(url).discover()` returns the
configured outbound endpoint without probing it.

## FastAPI

Install `mesh-python[fastapi]` and include the router on your existing FastAPI
app. Pass the `MeshRouter` that owns the node's identity and registered tools.

```python
from mesh.connections.fastapi import create_mesh_router
from mesh.router import MeshRouter

node = MeshRouter()
app.include_router(create_mesh_router(node))
```

`GET /.well-known/mesh` returns the node's `Greeting` as JSON. WebSocket clients
connect to `/mesh` and exchange one Mesh JSON envelope per text message, up to
1 MiB. The host ASGI server can enforce the same limit during frame assembly.
Peers can invoke tools registered on the node. Apply the host app's access
controls when exposing the WebSocket to untrusted clients.

## WebSocket LAN discovery

Pass the local node's `Greeting` to discover Mesh peers on active IPv4 subnets.
Discovery tries `ws://<address>:2047/` on each candidate and sends `hello` after
the WebSocket upgrade. It returns one open connection per node ID that answers
with a matching `-hello`. The peer supplies the identity exposed as
`peer_greeting`. The caller owns the returned connections and closes them with
`disconnect()`.

Use `network="192.168.1.0/24"` to select an on-link IPv4 subnet, or pass
`port` and `path` to match the peer's listener. On the listening side, wrap
accepted sockets in `WebSocketConnection`, dispatch `hello` through the
router, and send the resulting `-hello` with `send_faf()`.

```python
from mesh.connections import WebSocketConnection
from mesh.types import Greeting


async def discover_peers(identity: Greeting) -> None:
    """Print the Mesh identities announced by peers on this LAN.

    :param identity: Identity of the local Mesh node.
    """
    peers = await WebSocketConnection().discover(identity)
    try:
        for peer in peers:
            print(peer.endpoint, peer.peer_greeting)
    finally:
        for peer in peers:
            await peer.disconnect()
```

## Message exchange

`receive()` returns typed peer messages and unmatched acknowledgements.
`send(request)` waits for the corresponding acknowledgement, matching the
message type and reversed node IDs. The default response timeout is ten
seconds. The wire envelope has no request ID, so each connection allows
one request awaiting a response at a time and closes the session on a
response timeout. Use `send_faf()` to transmit acknowledgements or
messages for which the peer will send no reply.

For example, request capabilities from a known peer over WebSocket.

```python
from mesh.connections import WebSocketConnection
from mesh.messages import MeshMsg, MeshMsgCan, MeshMsgMeta


async def request_capabilities(url: str, local_id: str, peer_id: str) -> MeshMsg:
    """Request a peer's registered capabilities.

    :param url: WebSocket endpoint for the peer.
    :param local_id: ID of the requesting node.
    :param peer_id: ID of the peer node.
    :returns: The peer's capability acknowledgement.
    """
    connection = await WebSocketConnection(url).connect()
    try:
        return await connection.send(
            MeshMsgCan(
                meta=MeshMsgMeta(
                    version=0, node_from=local_id, node_to=peer_id, hops=[local_id],
                ),
                payload=MeshMsgCan.Payload(),
            )
        )
    finally:
        await connection.disconnect()
```
