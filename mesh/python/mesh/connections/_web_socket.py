"""Mesh transport over WebSocket text messages."""

from __future__ import annotations

import asyncio
import math
from ipaddress import IPv4Address, IPv4Interface, IPv4Network
from socket import AF_INET

import psutil
from websockets.asyncio.client import ClientConnection, connect
from websockets.asyncio.server import ServerConnection
from websockets.exceptions import ConnectionClosed, WebSocketException
from websockets.protocol import State

from ..messages import MeshMsgHello, MeshMsgHelloAck, MeshMsgMeta
from ..types import Greeting
from .__base import MAX_MESSAGE_BYTES, MESH_BASE_PORT, BaseConnection

_DISCOVERY_CONCURRENCY = 32


class WebSocketConnection(BaseConnection):
    """Connect to a Mesh WebSocket URL or wrap a server-side WebSocket."""

    def __init__(
        self, endpoint: str | ServerConnection | None = None, *, response_timeout: float = 10
    ) -> None:
        """Configure the WebSocket peer.

        :param endpoint: A ws/wss URL, an accepted socket, or None for LAN discovery.
        :param response_timeout: Maximum seconds to wait for an acknowledgement.
        """
        super().__init__(response_timeout=response_timeout)
        self._endpoint = endpoint
        self._socket: ClientConnection | ServerConnection | None = None
        self._lan_address: IPv4Address | None = None
        self._peer_greeting: Greeting | None = None

    @property
    def endpoint(self) -> str | ServerConnection | None:
        """Return the configured URL or accepted socket, if present."""
        return self._endpoint

    @property
    def peer_greeting(self) -> Greeting | None:
        """Return the identity announced by the peer during LAN discovery."""
        return self._peer_greeting

    async def discover(
        self,
        greeting: Greeting | None = None,
        *,
        network: IPv4Network | str | None = None,
        port: int = MESH_BASE_PORT,
        path: str = "/",
        probe_timeout: float = 1,
    ) -> list[WebSocketConnection]:
        """Find Mesh peers by exchanging hello messages on local IPv4 subnets.

        :param greeting: Local node identity. Without it, return the configured URL
            as a candidate without probing it.
        :param network: Optional on-link IPv4 subnet. Defaults to active non-loopback
            subnets, excluding addresses assigned to the scanning machine.
        :param port: The WebSocket port to try on each address.
        :param path: The WebSocket request path.
        :param probe_timeout: Maximum seconds for each upgrade and hello exchange.
        :returns: Open connections for verified peers, one per node ID. The caller
            must disconnect them.
        :raises ValueError: If the scan settings or local identity are invalid.
        """
        if greeting is None:
            return [self] if isinstance(self._endpoint, str) else []
        if not greeting.node_id:
            raise ValueError("Discovery requires a nonempty local node ID")
        if not 1 <= port <= 65535:
            raise ValueError("port must be between 1 and 65535")
        if not path.startswith("/") or "#" in path or any(c.isspace() for c in path):
            raise ValueError("path must be an absolute WebSocket path without a fragment")
        if not math.isfinite(probe_timeout) or probe_timeout <= 0:
            raise ValueError("probe_timeout must be positive and finite")

        requested = IPv4Network(network) if network is not None else None
        interface_stats = psutil.net_if_stats()
        interfaces = {
            IPv4Interface(f"{address.address}/{address.netmask}")
            for name, addresses in psutil.net_if_addrs().items()
            if name in interface_stats and interface_stats[name].isup
            for address in addresses
            if address.family == AF_INET and address.netmask and not address.ptp
        }
        if requested is not None:
            if not any(requested.subnet_of(interface.network) for interface in interfaces):
                raise ValueError("network must be on an active local IPv4 interface")
            subnets = {requested}
            excluded: set[IPv4Address] = set()
        else:
            subnets = {
                interface.network for interface in interfaces if not interface.ip.is_loopback
            }
            excluded = {interface.ip for interface in interfaces}

        addresses = (
            address
            for subnet in sorted(subnets)
            for address in subnet.hosts()
            if address not in excluded
        )
        hello = MeshMsgHello(
            meta=MeshMsgMeta(
                version=greeting.version,
                node_from=greeting.node_id,
                node_to="",
                hops=[greeting.node_id],
            ),
            payload=MeshMsgHello.Payload(greeting=greeting),
        )
        peers: dict[str, WebSocketConnection] = {}

        async def probe_addresses() -> None:
            """Take successive addresses from the shared scan and retain confirmed peers."""
            for address in addresses:
                connection = WebSocketConnection(
                    f"ws://{address}:{port}{path}", response_timeout=self._response_timeout
                )
                connection._lan_address = address
                keep_connection = False
                try:
                    async with asyncio.timeout(probe_timeout):
                        await connection.connect()
                        reply = await connection.send(hello)
                    if isinstance(reply, MeshMsgHelloAck) and reply.payload.error is None:
                        peer = reply.payload.greeting
                        if (
                            peer.node_id
                            and peer.node_id == reply.meta.node_from
                            and peer.node_id != greeting.node_id
                            and peer.node_id not in peers
                        ):
                            connection._peer_greeting = peer
                            peers[peer.node_id] = connection
                            keep_connection = True
                except (OSError, ValueError, WebSocketException):
                    continue
                finally:
                    if not keep_connection:
                        await connection.disconnect()

        try:
            async with asyncio.TaskGroup() as tasks:
                for _ in range(_DISCOVERY_CONCURRENCY):
                    tasks.create_task(probe_addresses())
        except BaseException:
            await asyncio.gather(*(peer.disconnect() for peer in peers.values()))
            raise
        return list(peers.values())

    async def _open(self) -> None:
        """Dial the configured URL or take ownership of the accepted socket."""
        if isinstance(self._endpoint, str):
            if self._lan_address is None:
                self._socket = await connect(self._endpoint, max_size=MAX_MESSAGE_BYTES)
            else:
                # An explicit TCP host also prevents cross-origin redirects.
                self._socket = await connect(
                    self._endpoint, max_size=MAX_MESSAGE_BYTES, proxy=None,
                    host=str(self._lan_address), close_timeout=1,
                )
        elif self._endpoint is None:
            raise ValueError("A WebSocket endpoint is required to connect")
        elif self._endpoint.state is State.OPEN:
            self._socket = self._endpoint
        else:
            raise ConnectionError("Accepted WebSocket is no longer open")

    async def _close(self) -> None:
        """Close the underlying WebSocket."""
        if self._socket is not None:
            await self._socket.close()
            self._socket = None
            self._peer_greeting = None

    async def _read_frame(self) -> str:
        """Read JSON from one WebSocket text message."""
        assert self._socket is not None
        message = await self._socket.recv()
        if not isinstance(message, str):
            raise TypeError("Mesh WebSocket messages must use text frames")
        if len(message.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ValueError("Mesh message exceeds the transport size limit")
        return message

    async def _write_frame(self, payload: str) -> None:
        """Write JSON in one WebSocket text message.

        :param payload: Serialized mesh message.
        """
        assert self._socket is not None
        try:
            async with asyncio.timeout(10):
                await self._socket.send(payload)
        except ConnectionClosed as error:
            raise ConnectionError("WebSocket closed") from error
