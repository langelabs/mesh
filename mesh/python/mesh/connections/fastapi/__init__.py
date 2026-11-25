"""Mount Mesh discovery and WebSocket routes on an existing FastAPI app."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ...router import MeshRouter
    from ._router import MeshAPIRouter


def create_mesh_router(node: MeshRouter) -> MeshAPIRouter:
    """Create a FastAPI router bound to a configured Mesh node.

    :param node: Mesh node that supplies the greeting and handles messages.
    :returns: The router to pass to ``FastAPI.include_router``.
    """
    from ._router import MeshAPIRouter
    from .endopints._websocket import mesh_websocket
    from .endopints._well_known import mesh_greeting

    router = MeshAPIRouter(node)
    router.add_api_route("/.well-known/mesh", mesh_greeting, methods=["GET"])
    router.add_api_websocket_route("/mesh", mesh_websocket, name="mesh")
    return router
