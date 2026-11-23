"""Shared typed message exchange for asynchronous mesh transports."""

from __future__ import annotations

import asyncio
import math
from abc import ABC, abstractmethod
from functools import partial
from typing import Annotated, Protocol, Self, runtime_checkable

from pydantic import Field, TypeAdapter

from ..messages import (
    MeshMsg,
    MeshMsgCan,
    MeshMsgCanAck,
    MeshMsgDo,
    MeshMsgDoAck,
    MeshMsgFriends,
    MeshMsgFriendsAck,
    MeshMsgHello,
    MeshMsgHelloAck,
)

# Sum of ASCII values in "THIS-IS-A-LANGE-LABS-MESH-NODE".
MESH_BASE_PORT = 2047
MAX_MESSAGE_BYTES = 1024 * 1024
_MAX_UNSOLICITED_MESSAGES = 64

_MESSAGE_ADAPTER = TypeAdapter(
    Annotated[
        MeshMsgHello
        | MeshMsgHelloAck
        | MeshMsgFriends
        | MeshMsgFriendsAck
        | MeshMsgCan
        | MeshMsgCanAck
        | MeshMsgDo
        | MeshMsgDoAck,
        Field(discriminator="msg"),
    ]
)


@runtime_checkable
class HandlerProtocol(Protocol):
    """Handle messages received by a mesh node."""

    async def hande_message(self, msg: MeshMsg) -> MeshMsg | MeshMsg.Payload:
        """Process an incoming mesh message.

        :param msg: Message to handle.
        :returns: Reply message or acknowledgement payload.
        """
        ...


class BaseConnection(ABC):
    """Exchange mesh messages with one reader and one in-flight request."""

    def __init__(self, *, response_timeout: float) -> None:
        """Initialize an asyncio connection.

        :param response_timeout: Maximum seconds to wait for an acknowledgement.
        :raises ValueError: If the timeout is not positive and finite.
        """
        if not math.isfinite(response_timeout) or response_timeout <= 0:
            raise ValueError("response_timeout must be positive and finite")
        self._response_timeout = response_timeout
        self._lifecycle_lock = asyncio.Lock()
        self._request_lock = asyncio.Lock()
        self._write_lock = asyncio.Lock()
        self._reader: asyncio.Task[None] | None = None
        self._incoming: asyncio.Queue[MeshMsg | Exception] | None = None
        self._pending: tuple[MeshMsg, asyncio.Future[MeshMsg]] | None = None

    async def connect(self) -> Self:
        """Open the transport and start its reader on the current event loop.

        :returns: The connected instance.
        """
        async with self._lifecycle_lock:
            if self._reader is not None and not self._reader.done():
                return self

            async with self._write_lock:
                if self._reader is not None:
                    await self._close()
                    self._reader = None
                await self._open()
                self._incoming = asyncio.Queue()
                self._reader = asyncio.create_task(self._read_messages(self._incoming))
                self._reader.add_done_callback(
                    partial(self._reader_finished, self._incoming)
                )
        return self

    async def disconnect(self) -> None:
        """Close the transport and wake callers waiting for a message."""
        await self._disconnect()

    async def _disconnect(self, reader: asyncio.Task[None] | None = None) -> None:
        """Close the current session or the specific session that failed.

        :param reader: Restrict closure to the session owned by this read task.
        """
        async with self._lifecycle_lock, self._write_lock:
            if reader is not None and reader is not self._reader:
                return
            if self._reader is not None:
                self._reader.cancel()
                await asyncio.gather(self._reader, return_exceptions=True)
                await self._close()
                self._reader = None

    async def receive(self) -> MeshMsg:
        """Read the next message that was not consumed by a pending send.

        :returns: A validated, concrete mesh message.
        :raises ConnectionError: If the session has ended or has not been opened.
        """
        incoming = self._incoming
        if incoming is None:
            raise ConnectionError("Mesh transport is not connected")
        item = await incoming.get()
        if isinstance(item, Exception):
            incoming.put_nowait(item)
            raise ConnectionError("Mesh transport closed") from item
        return item

    async def send_faf(self, msg: MeshMsg) -> None:
        """Write a message without waiting for an acknowledgement.

        :param msg: Mesh message to transmit.
        """
        payload = msg.model_dump_json()
        if len(payload.encode("utf-8")) > MAX_MESSAGE_BYTES:
            raise ValueError("Mesh message exceeds the transport size limit")

        reader = self._reader
        async with self._write_lock:
            if reader is None or reader is not self._reader or reader.done():
                raise ConnectionError("Mesh transport is not connected")
            # Keep a cancelled caller from interrupting a partially written frame.
            write = asyncio.create_task(self._write_frame(payload))
            try:
                await asyncio.shield(write)
            except asyncio.CancelledError:
                await asyncio.gather(write, return_exceptions=True)
                raise
            except OSError as error:
                # Release the write lock before shutting down the session.
                failure = error
            else:
                return
        await self._disconnect(reader)
        raise ConnectionError("Mesh transport write failed") from failure

    async def send(self, msg: MeshMsg) -> MeshMsg:
        """Send a request and wait for its matching acknowledgement.

        :param msg: Mesh request to transmit.
        :returns: The acknowledgement with reversed sender and recipient. An
            unaddressed hello can be acknowledged by an unknown sender.
        :raises ValueError: If an acknowledgement is passed as a request.
        :raises TimeoutError: If the peer does not acknowledge the request in time.
        """
        if msg.msg.startswith("-"):
            raise ValueError("Use send_faf to transmit an acknowledgement")

        reader = self._reader
        async with self._request_lock:
            if reader is None or reader is not self._reader or reader.done():
                raise ConnectionError("Mesh transport is not connected")
            reply = asyncio.get_running_loop().create_future()
            self._pending = (msg, reply)
            try:
                await self.send_faf(msg)
                return await asyncio.wait_for(reply, self._response_timeout)
            except (TimeoutError, asyncio.CancelledError):
                # Without request IDs, a late reply could be matched to a later send.
                await self._disconnect(reader)
                raise
            finally:
                self._pending = None
                if reply.done() and not reply.cancelled():
                    reply.exception()
                else:
                    reply.cancel()

    async def _read_messages(
        self, incoming: asyncio.Queue[MeshMsg | Exception]
    ) -> None:
        """Validate each frame and route it to the pending request or inbox.

        :param incoming: Queue for peer requests and unmatched acknowledgements.
        """
        while True:
            msg = _MESSAGE_ADAPTER.validate_json(await self._read_frame())
            if self._pending is not None:
                request, reply = self._pending
                if (
                    not reply.done()
                    and msg.msg == f"-{request.msg}"
                    and (
                        msg.meta.node_from == request.meta.node_to
                        or (isinstance(request, MeshMsgHello) and request.meta.node_to == "")
                    )
                    and msg.meta.node_to == request.meta.node_from
                ):
                    reply.set_result(msg)
                    continue

            if incoming.qsize() >= _MAX_UNSOLICITED_MESSAGES:
                raise ConnectionError("Mesh receive queue is full")
            incoming.put_nowait(msg)

    def _reader_finished(
        self, incoming: asyncio.Queue[MeshMsg | Exception], reader: asyncio.Task[None]
    ) -> None:
        """Notify all waiting callers when the session ends.

        :param incoming: Inbox owned by the completed session.
        :param reader: Completed session reader.
        """
        error = None if reader.cancelled() else reader.exception()
        failure = ConnectionError("Mesh transport closed")
        failure.__cause__ = error
        incoming.put_nowait(failure)
        if reader is self._reader and self._pending is not None:
            _, reply = self._pending
            if not reply.done():
                reply.set_exception(failure)

    @abstractmethod
    async def discover(self) -> list[BaseConnection]:
        """Find candidate peer connections for this transport.

        :returns: Connections available to open.
        """

    @abstractmethod
    async def _open(self) -> None:
        """Open the transport resource."""

    @abstractmethod
    async def _close(self) -> None:
        """Release the transport resource."""

    @abstractmethod
    async def _read_frame(self) -> str | bytes:
        """Return one complete JSON message."""

    @abstractmethod
    async def _write_frame(self, payload: str) -> None:
        """Write one complete JSON message.

        :param payload: Serialized mesh message.
        """
