"""Worker websocket entrypoint for the standalone mesh service."""

import asyncio
from contextlib import suppress

from lange.contracts.mesh import MeshMessage
from pydantic import ValidationError
from starlette.websockets import WebSocket, WebSocketDisconnect, WebSocketState

from mesh_service import state
from mesh_service.config import Settings, get_settings
from mesh_service.router.worker import MeshWorker

from .__router import workers_router


def _is_authorized(headers: object, settings: Settings) -> bool:
    """Return whether a worker websocket request is authorized.

    :param headers: Websocket request headers.
    :param settings: Runtime mesh service settings.
    :returns: ``True`` when auth is disabled or the bearer secret matches.
    """
    if settings.worker_secret is None:
        return True
    authorization = getattr(headers, "get", lambda _: None)("authorization")
    return authorization == f"Bearer {settings.worker_secret}"


@workers_router.websocket("/entrypoint")
async def worker_entrypoint(websocket: WebSocket) -> None:
    """Accept one relay worker websocket and attach it to the mesh router.

    :param websocket: Worker websocket connection accepted by FastAPI.
    """
    settings = get_settings()
    if not _is_authorized(websocket.headers, settings):
        await websocket.close(code=1008, reason="Worker authorization failed.")
        return

    mesh_worker = MeshWorker()
    is_registered = False

    try:
        async def read_from_worker() -> None:
            """Read messages from the worker websocket and forward them."""
            nonlocal is_registered
            while True:
                raw_message = await websocket.receive_json()
                try:
                    message = MeshMessage.model_validate(raw_message)
                except ValidationError as error:
                    if websocket.application_state == WebSocketState.CONNECTED:
                        await websocket.close(code=1008, reason="Invalid mesh message.")
                    raise WebSocketDisconnect(code=1008) from error

                try:
                    response = await state.MESH_ROUTER.handle_message_from_worker(
                        worker=mesh_worker,
                        message=message,
                        websocket=websocket,
                    )
                except (RuntimeError, ValueError) as error:
                    if websocket.application_state == WebSocketState.CONNECTED:
                        await websocket.close(code=1008, reason=str(error))
                    raise WebSocketDisconnect(code=1008) from error

                if response is not None:
                    await websocket.send_json(response.model_dump_json())

                if message.status == "ready" and not is_registered:
                    if mesh_worker.name is None or mesh_worker.timeout is None:
                        if websocket.application_state == WebSocketState.CONNECTED:
                            await websocket.close(
                                code=1008,
                                reason="Relay worker registration is required.",
                            )
                        raise WebSocketDisconnect(code=1008)
                    state.MESH_ROUTER.register_worker(mesh_worker.name, mesh_worker)
                    is_registered = True

        async def write_to_worker() -> None:
            """Write queued mesh messages to the worker websocket."""
            async for message in mesh_worker.listen():
                await websocket.send_json(message.model_dump_json())

        await websocket.accept()

        try:
            read_task = asyncio.create_task(read_from_worker())
            write_task = asyncio.create_task(write_to_worker())
            done, pending = await asyncio.wait(
                {read_task, write_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in pending:
                with suppress(asyncio.CancelledError):
                    await task
            for task in done:
                with suppress(WebSocketDisconnect, asyncio.CancelledError):
                    task.result()
        finally:
            if websocket.application_state == WebSocketState.CONNECTED:
                with suppress(RuntimeError):
                    await websocket.close()
    finally:
        if is_registered and mesh_worker.name is not None:
            state.MESH_ROUTER.unregister_worker(mesh_worker.name, mesh_worker)
