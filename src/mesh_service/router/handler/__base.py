from abc import ABC
import abc
from asyncio import Queue
import uuid

from lange.contracts.mesh import MeshMessage

from mesh_service.router.worker import MeshWorker


class BaseHandler(ABC):
    """Base class for mesh worker message handlers."""

    @staticmethod
    @abc.abstractmethod
    async def handle(
        message: MeshMessage,
        worker: MeshWorker,
        result_map: dict[uuid.UUID, Queue[MeshMessage]],
    ) -> MeshMessage | None:
        """Handle one worker message.

        :param message: Mesh message received from the worker.
        :param worker: Connected worker session.
        :param result_map: Pending relay response queues by message ID.
        :returns: Optional response message to send immediately.
        """
        pass
