from asyncio import Queue
from typing import AsyncGenerator

from lange.contracts.mesh import MeshMessage


class MeshWorker:
    """Connected worker session managed by the mesh computer."""

    def __init__(self) -> None:
        """Initialize the outbound message queue for one mesh worker."""
        self.queue: Queue[MeshMessage] = Queue()
        self.is_ready = False
        self.name: "str | None" = None
        self.timeout: "float | None" = None

    async def listen(self) -> AsyncGenerator[MeshMessage, None]:
        """Yield queued mesh messages that should be sent to the worker.

        :returns: Async stream of mesh messages for the connected mesh worker.
        """
        while True:
            item = await self.queue.get()
            yield item
