from asyncio import Queue
import uuid

from lange.contracts.mesh import MeshMessage

from mesh_service.router.worker import MeshWorker

from .__base import BaseHandler


class PingHandler(BaseHandler):
    """Handle worker ping messages."""

    @staticmethod
    async def handle(
        message: MeshMessage,
        worker: MeshWorker,
        result_map: dict[uuid.UUID, Queue[MeshMessage]],
    ) -> MeshMessage | None:
        """Return a lightweight ready response to a ping.

        :param message: Ping message from the worker.
        :param worker: Connected worker session.
        :param result_map: Pending relay response queues by message ID.
        :returns: Ready response message.
        """
        del message, worker, result_map
        return MeshMessage(status="ready", data=None, type="manage")
