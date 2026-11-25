"""Advertise a node's Mesh identity over HTTP."""

from typing import Annotated

from fastapi import Depends

from ....types import Greeting
from .._router import MeshAPIRouter, get_mesh_router


async def mesh_greeting(
    router: Annotated[MeshAPIRouter, Depends(get_mesh_router)],
) -> Greeting:
    """Advertise the local Mesh node to prospective peers.

    :param router: FastAPI router bound to the local Mesh node.
    :returns: The local node's greeting.
    """
    return router.node.get_greeting()
