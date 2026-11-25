"""Handle Mesh messages on an accepted FastAPI WebSocket."""

from typing import Annotated

from fastapi import Depends, WebSocket, WebSocketDisconnect, status
from pydantic import ValidationError

from ....messages import MeshMsg
from ...__base import MAX_MESSAGE_BYTES, _MESSAGE_ADAPTER
from .._router import MeshAPIRouter, get_mesh_router


async def mesh_websocket(
    websocket: WebSocket,
    router: Annotated[MeshAPIRouter, Depends(get_mesh_router)],
) -> None:
    """Dispatch each text message and send any Mesh reply on the same socket.

    :param websocket: Peer connection supplied by the host app.
    :param router: FastAPI router bound to the local Mesh node.
    """
    try:
        await websocket.accept()
        while True:
            frame = await websocket.receive()
            if frame["type"] == "websocket.disconnect":
                return

            text = frame.get("text")
            if text is None:
                await websocket.close(code=status.WS_1003_UNSUPPORTED_DATA)
                return
            if len(text.encode("utf-8")) > MAX_MESSAGE_BYTES:
                await websocket.close(code=status.WS_1009_MESSAGE_TOO_BIG)
                return
            try:
                message = _MESSAGE_ADAPTER.validate_json(text)
            except ValidationError:
                await websocket.close(code=status.WS_1007_INVALID_FRAME_PAYLOAD_DATA)
                return

            reply = await router.node.hande_message(message)
            if isinstance(reply, MeshMsg):
                payload = reply.model_dump_json()
                if len(payload.encode("utf-8")) > MAX_MESSAGE_BYTES:
                    await websocket.close(code=status.WS_1009_MESSAGE_TOO_BIG)
                    return
                await websocket.send_text(payload)
    except WebSocketDisconnect:
        return
