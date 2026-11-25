"""Bind the mounted Mesh router to each HTTP or WebSocket connection."""

from typing import cast

from fastapi import APIRouter, Depends
from fastapi.requests import HTTPConnection

from ...router import MeshRouter


class MeshAPIRouter(APIRouter):
    """FastAPI router bound to a Mesh node."""

    def __init__(self, node: MeshRouter) -> None:
        """Configure a router and register its connection dependency.

        :param node: Mesh node served by this router.
        """
        self.node = node
        super().__init__(dependencies=[Depends(self._bind_to_connection)])

    async def _bind_to_connection(self, connection: HTTPConnection) -> None:
        """Make this router available to dependencies on the current connection.

        :param connection: Incoming HTTP request or WebSocket connection.
        """
        connection.state.mesh_api_router = self


async def get_mesh_router(connection: HTTPConnection) -> MeshAPIRouter:
    """Resolve the Mesh router serving the current connection.

    :param connection: Incoming HTTP request or WebSocket connection.
    :returns: The router that registered the endpoint.
    """
    return cast(MeshAPIRouter, connection.state.mesh_api_router)
