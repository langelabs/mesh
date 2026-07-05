from asyncio import Queue
import uuid

from lange.contracts.mesh import MeshMessage
from lange.contracts.worker import MeshWorkerConfig, MeshWorkerRegistration

from mesh_service.config import get_settings
from mesh_service.router.worker import MeshWorker
from mesh_service.utils.name import is_valid_relay_name

from .__base import BaseHandler


class HelloHandler(BaseHandler):
    """Handle worker hello and registration payloads."""

    @staticmethod
    async def handle(
        message: MeshMessage,
        worker: MeshWorker,
        result_map: dict[uuid.UUID, Queue[MeshMessage]],
    ) -> MeshMessage | None:
        """Register relay worker metadata from a hello message.

        :param message: Hello message from the worker.
        :param worker: Connected worker session.
        :param result_map: Pending relay response queues by message ID.
        :returns: Hello response containing public relay configuration.
        :raises RuntimeError: If the hello payload is not a relay registration.
        :raises ValueError: If the registration is invalid.
        """
        del result_map
        # guards
        if not isinstance(message.data, MeshWorkerRegistration):
            raise RuntimeError("No relay worker registration in hello message.")
        if not is_valid_relay_name(message.data.name):
            raise ValueError("Relay name must be DNS-label-safe.")
        if message.data.request_timeout_seconds <= 0:
            raise ValueError("Relay request timeout must be greater than 0.")

        # set up the worker on the server
        worker.name = message.data.name
        worker.timeout = message.data.request_timeout_seconds

        # set up the worker remote
        settings = get_settings()
        mesh_public_scheme = settings.mesh_public_scheme.strip().rstrip(":/")
        mesh_public_base_domain = settings.mesh_base_domain.strip().strip(".")
        config = MeshWorkerConfig(
            remote_relay_address=(
                f"{mesh_public_scheme}://{message.data.name}.{mesh_public_base_domain}/"
            ),
            type="REST",
        )

        return MeshMessage(status="hello", data=config)
