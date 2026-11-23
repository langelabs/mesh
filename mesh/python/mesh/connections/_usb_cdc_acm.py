"""Mesh transport over an OS-provided USB CDC ACM serial port."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import TypeVar

from serial import Serial, SerialTimeoutException
from serial.tools.list_ports import comports

from .__base import MAX_MESSAGE_BYTES, BaseConnection

_Result = TypeVar("_Result")


async def _serial_call(operation: Callable[[], _Result]) -> _Result:
    """Run a blocking serial operation and let it finish before propagating cancellation.

    :param operation: Serial call to run in a worker thread.
    :returns: Result of the serial call.
    """
    task = asyncio.create_task(asyncio.to_thread(operation))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        await asyncio.gather(task, return_exceptions=True)
        raise


class UsbCdcAcmConnection(BaseConnection):
    """Read and write newline-delimited JSON over a USB serial connection."""

    def __init__(
        self,
        port: str | None = None,
        *,
        baudrate: int = 115200,
        response_timeout: float = 10,
    ) -> None:
        """Configure a serial port or create a USB discovery instance.

        :param port: OS serial device path or COM port name.
        :param baudrate: Baud rate to configure on the port.
        :param response_timeout: Maximum seconds to wait for an acknowledgement.
        """
        super().__init__(response_timeout=response_timeout)
        self.port = port
        self.baudrate = baudrate
        self._serial: Serial | None = None
        self._buffer = bytearray()

    async def discover(self) -> list[UsbCdcAcmConnection]:
        """List USB serial candidates reported by the operating system.

        :returns: Unopened connections using the configured baud rate and timeout.
        """
        return [
            UsbCdcAcmConnection(
                port.device,
                baudrate=self.baudrate,
                response_timeout=self._response_timeout,
            )
            for port in await asyncio.to_thread(comports)
            if port.vid is not None and port.pid is not None
        ]

    async def _open(self) -> None:
        """Open the configured serial port with bounded writes and nonblocking reads."""
        if self.port is None:
            raise ValueError("A serial port is required to connect")
        serial = Serial(baudrate=self.baudrate, timeout=0, write_timeout=2)
        serial.port = self.port
        try:
            await _serial_call(serial.open)
        except (Exception, asyncio.CancelledError):
            await _serial_call(serial.close)
            raise
        self._serial = serial
        self._buffer.clear()

    async def _close(self) -> None:
        """Close the serial port and discard any incomplete frame."""
        if self._serial is not None:
            await _serial_call(self._serial.close)
            self._serial = None
        self._buffer.clear()

    async def _read_frame(self) -> bytes:
        """Read a complete LF- or CRLF-terminated JSON record."""
        assert self._serial is not None
        while True:
            newline = self._buffer.find(b"\n")
            if newline >= 0:
                message = bytes(self._buffer[:newline]).removesuffix(b"\r")
                del self._buffer[: newline + 1]
                if len(message) > MAX_MESSAGE_BYTES:
                    raise ValueError("Mesh message exceeds the transport size limit")
                return message
            if len(self._buffer) > MAX_MESSAGE_BYTES + 1:
                raise ValueError("Mesh message exceeds the transport size limit")
            chunk = self._serial.read(4096)
            if chunk:
                self._buffer.extend(chunk)
            else:
                await asyncio.sleep(0.01)

    async def _write_frame(self, payload: str) -> None:
        """Write one UTF-8 JSON record followed by LF.

        :param payload: Serialized mesh message.
        """
        assert self._serial is not None
        frame = payload.encode("utf-8") + b"\n"
        written = await asyncio.to_thread(self._serial.write, frame)
        if written != len(frame):
            raise SerialTimeoutException("Incomplete Mesh serial write")
