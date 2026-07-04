"""Helpers for translating public HTTP requests to relay worker messages."""

import base64
from collections.abc import Mapping, Sequence

from fastapi import HTTPException, Request, Response
from lange.contracts.mesh import MeshRelayRequest, MeshRelayResponse
from starlette import status

from .headers import PROXY_CONTROLLED_HEADERS, sanitize_request_headers


def build_query_param_map(query_items: Sequence[tuple[str, str]]) -> dict[str, list[str]]:
    """Build a repeated-key query parameter map from request query items.

    :param query_items: Ordered query parameter key/value pairs from Starlette.
    :returns: Query parameters grouped by key while preserving repeated values.
    """
    query_params: dict[str, list[str]] = {}
    for key, value in query_items:
        query_params.setdefault(key, []).append(value)
    return query_params


def normalize_forwarded_path(path: str | None) -> str:
    """Return the relay request path with one leading slash.

    :param path: Route-captured path segment, or ``None`` for root requests.
    :returns: Normalized relay request path.
    """
    if not path:
        return ""
    normalized_path = path.strip()
    if not normalized_path:
        return "/"
    return f"/{normalized_path.lstrip('/')}"


async def build_relay_request(request: Request, path: str | None) -> MeshRelayRequest:
    """Build one relay request payload from an incoming HTTP request.

    :param request: Incoming public mesh HTTP request.
    :param path: Route-captured path segment, or ``None`` for root requests.
    :returns: Relay request payload for the connected worker.
    """
    body = await request.body()
    return MeshRelayRequest(
        method=request.method.upper(),
        path=normalize_forwarded_path(path),
        headers=sanitize_request_headers(request.headers),
        body=base64.b64encode(body).decode("ascii") if body else None,
        body_encoding="base64" if body else None,
        query_params=build_query_param_map(list(request.query_params.multi_items())),
        query_string=request.url.query or None,
    )


def _base64_decoded_size(value: str) -> int:
    """Return the decoded byte size for one base64 payload without decoding it.

    :param value: Base64-encoded payload.
    :returns: Decoded payload size in bytes.
    """
    normalized_value = value.strip()
    if not normalized_value:
        return 0
    padding = len(normalized_value) - len(normalized_value.rstrip("="))
    return (len(normalized_value) * 3 // 4) - padding


def build_http_response(
    relay_response: MeshRelayResponse,
    method: str,
    max_body_bytes: int = 20 * 1024 * 1024,
) -> Response:
    """Translate one relay worker response into an HTTP response.

    :param relay_response: Relay response payload returned by a worker.
    :param method: Original public HTTP method.
    :param max_body_bytes: Maximum decoded response body size.
    :returns: HTTP response for the public request.
    :raises HTTPException: If the relay response body is too large.
    """
    body = b""
    if (
        relay_response.body is not None
        and method.upper() != "HEAD"
        and relay_response.status not in {204, 304}
    ):
        if relay_response.body_encoding == "base64":
            if _base64_decoded_size(relay_response.body) > max_body_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Relay response body is too large.",
                )
            body = base64.b64decode(relay_response.body.encode("ascii"))
        else:
            if len(relay_response.body.encode("utf-8")) > max_body_bytes:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Relay response body is too large.",
                )
            body = relay_response.body.encode("utf-8")

    return Response(
        content=body,
        status_code=relay_response.status,
        headers=sanitize_response_headers(relay_response.headers),
    )


def sanitize_response_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Remove proxy-controlled headers from relay worker responses.

    :param headers: Relay worker response headers.
    :returns: Headers safe to return to the public client.
    """
    return {
        str(header_name): str(header_value)
        for header_name, header_value in headers.items()
        if str(header_name).lower() not in PROXY_CONTROLLED_HEADERS
    }
