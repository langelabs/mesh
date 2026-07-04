from asyncio import Queue, wait_for
from logging import getLogger
import random
import uuid

from starlette.websockets import WebSocket

from lange.contracts.mesh import MeshMessage
from lange.contracts.mesh.relay import MeshRelayRequest, MeshRelayResponse

from .handler import HelloHandler, PingHandler, ReadyHandler, ResponseHandler
from .worker import MeshWorker
from mesh_service.utils.messages import dump_mesh_message

logger = getLogger("com.lange-labs.mesh")


class MeshRouter:
    """Route mesh compute requests to connected worker pools."""

    def __init__(self) -> None:
        """Initialize worker pools and request result listeners."""
        self.workers: dict[str, list[MeshWorker]] = {}
        self.result_map: dict[uuid.UUID, Queue[MeshMessage]] = dict()

    def register_worker(self, name: str, worker: MeshWorker) -> None:
        """Register one connected compute worker in a keyed pool.

        :param name: Compute worker pool name, defaults to ``default``.
        :param worker: Connected compute worker session to add to the pool.
        """
        self.workers.setdefault(name, []).append(worker)

    def unregister_worker(self, name: str, worker: MeshWorker) -> None:
        """Unregister one connected compute worker from a keyed pool.

        :param name: Compute worker pool name, currently ``default``.
        :param worker: Connected compute worker session to remove from the pool.
        """
        workers = self.workers[name]
        workers.remove(worker)
        if len(workers) == 0:
            del self.workers[name]

    def _get_worker(self, name: str) -> MeshWorker:
        """Return one compute worker selected from the requested keyed pool.

        :param name: Compute worker pool key.
        :returns: Randomly selected compute worker connection.
        :raises RuntimeError: If no workers are registered for the key.
        """
        workers = self.workers.get(name, [])
        if len(workers) == 0:
            raise RuntimeError("No workers registered for key {}".format(name))
        return random.choice(workers)

    async def handle_message_from_worker(
            self,
            message: MeshMessage,
            worker: MeshWorker,
            websocket: WebSocket,
    ) -> None:
        """Handle one control or response message received from a compute worker.

        :param message: Parsed mesh message sent by the connected compute worker.
        :param worker: The compute worker from which the message was received.
        :param websocket: Compute worker websocket used for immediate control replies.
        :param settings: Runtime API settings used to build relay worker config.
        :raises RuntimeError: If a response has no waiting listener.
        :raises NotImplementedError: If the message status is unsupported.
        """
        logger.info("Handle compute [%s] Mesh Message", message.status)

        if message.status == "ping":
            response = await PingHandler.handle(message=message, worker=worker, result_map=self.result_map)
        elif message.status == "hello":
            response = await HelloHandler.handle(message=message, worker=worker, result_map=self.result_map)
        elif message.status == "response":
            response = await ResponseHandler.handle(message=message, worker=worker, result_map=self.result_map)
        elif message.status == "ready":
            response = await ReadyHandler.handle(message=message, worker=worker, result_map=self.result_map)
        else:
            raise NotImplementedError("Message status not implemented Status: {}".format(message.status))

        # return the response if one is generated
        if response is not None:
            await websocket.send_json(dump_mesh_message(response))

    async def relay_rest(
            self,
            name: str,
            request: MeshRelayRequest,
    ) -> MeshRelayResponse:
        """Send one REST request to a keyed compute worker and await its response.

        :param key: Compute worker pool key.
        :param request: REST request payload to forward.
        :returns: REST response payload published by the compute worker.
        :raises RuntimeError: If no compute workers serve the key or the response
            has an unexpected payload type.
        :raises TimeoutError: If no response arrives before the worker-owned timeout.
        """
        worker = self._get_worker(name)
        if worker.timeout is None:
            raise RuntimeError("No relay worker request timeout registered")
        message = MeshMessage(status="request", data=request)
        result_queue: Queue[MeshMessage] = Queue()
        self.result_map[message.id] = result_queue

        try:
            await worker.queue.put(message)
            result = await wait_for(
                result_queue.get(),
                timeout=worker.timeout,
            )
        finally:
            self.result_map.pop(message.id, None)

        if not isinstance(result.data, MeshRelayResponse):
            raise RuntimeError("No REST response data returned")
        return result.data
