from asyncio import Queue
import uuid

from lange.contracts.mesh import MeshMessage

from mesh_service.router.worker import MeshWorker

from .__base import BaseHandler


class ResponseHandler(BaseHandler):
    """Handle relay response messages from workers."""

    @staticmethod
    async def handle(
        message: MeshMessage,
        worker: MeshWorker,
        result_map: dict[uuid.UUID, Queue[MeshMessage]],
    ) -> MeshMessage | None:
        """Publish one worker response to a waiting relay request queue.

        :param message: Response message from the worker.
        :param worker: Connected worker session.
        :param result_map: Pending relay response queues by message ID.
        :returns: ``None`` because responses are consumed by waiting requests.
        """
        del worker
        if message.id in result_map:
            await result_map[message.id].put(message)
        return None
