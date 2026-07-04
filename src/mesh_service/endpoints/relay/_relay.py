"""Public HTTP relay endpoints for the standalone mesh service."""

from fastapi import HTTPException, Request, Response
from starlette import status

from mesh_service import state
from mesh_service.config import get_settings
from mesh_service.utils.host import resolve_mesh_host
from mesh_service.utils.methods import HTTP_METHODS
from mesh_service.utils.name import extract_mesh_name
from mesh_service.utils.relay import build_http_response, build_relay_request

from .__router import relay_router


@relay_router.api_route("/", methods=HTTP_METHODS)
@relay_router.api_route("/{path:path}", methods=HTTP_METHODS)
async def relay_mesh_request(
    request: Request,
    path: str = "",
) -> Response:
    """Forward one public mesh host request to a connected relay worker.

    :param request: Incoming public HTTP request.
    :param path: Incoming path segment captured by FastAPI.
    :returns: HTTP response returned by the relay worker.
    :raises HTTPException: If the host is not a valid mesh relay host.
    """
    settings = get_settings()
    host = resolve_mesh_host(request)
    name = extract_mesh_name(host, settings.mesh_base_domain)
    if name is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND)

    relay_request = await build_relay_request(request, path)
    try:
        relay_response = await state.MESH_ROUTER.relay_rest(name, relay_request)
    except RuntimeError as error:
        if "No workers registered" in str(error):
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="No relay worker is connected for this name.",
            ) from error
        raise
    except TimeoutError as error:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Relay worker did not return a response in time.",
        ) from error

    return build_http_response(relay_response, request.method)
