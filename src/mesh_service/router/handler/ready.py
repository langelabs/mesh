from asyncio import Queue
import uuid

from lange.contracts.mesh import MeshMessage

from mesh_service.router.worker import MeshWorker

from .__base import BaseHandler


class ReadyHandler(BaseHandler):
    """Handle worker ready messages."""

    @staticmethod
    async def handle(
        message: MeshMessage,
        worker: MeshWorker,
        result_map: dict[uuid.UUID, Queue[MeshMessage]],
    ) -> MeshMessage | None:
        """Mark a worker session as ready.

        :param message: Ready message from the worker.
        :param worker: Connected worker session.
        :param result_map: Pending relay response queues by message ID.
        :returns: ``None`` because ready does not emit a direct response.
        """
        del message, result_map
        worker.is_ready = True
        return None
