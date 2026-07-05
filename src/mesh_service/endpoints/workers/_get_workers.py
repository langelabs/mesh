from pydantic import BaseModel

from mesh_service import state
from mesh_service.views import WorkerView

from .__router import workers_router


class GetWorkersResponse(BaseModel):
    """Response body for the workers collection endpoint."""

    workers: list[WorkerView]


@workers_router.get("")
async def get_workers() -> GetWorkersResponse:
    """Return all currently registered mesh workers.

    :returns: Workers grouped by the in-process mesh router flattened into a
        serializable collection response.
    """
    return GetWorkersResponse(
        workers=[
            WorkerView(
                name=worker.name or "unknown",
                timeout=worker.timeout,
                ip_address=worker.ip_address,
                status="ready" if worker.is_ready else "pending",
            )
            for workers in state.MESH_ROUTER.workers.values()
            for worker in workers
            if worker.name is not None and worker.timeout is not None
        ]
    )
