from fastapi import Request

from mesh_service.config import get_settings

from .name import extract_mesh_name

def resolve_mesh_host(request: Request) -> str:
    """
    Resolve the effective public mesh host for one proxied request.

    :param request: Incoming public or reverse-proxied HTTP request.
    :returns: Host value used for mesh name extraction.
    """
    host = request.headers.get("host", "")
    base_domain = get_settings().mesh_base_domain
    if extract_mesh_name(host, base_domain) is not None:
        return host

    forwarded_host = request.headers.get("x-forwarded-host", "")
    if extract_mesh_name(forwarded_host, base_domain) is not None:
        return forwarded_host

    return host
