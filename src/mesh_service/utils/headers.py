from typing import Final, Mapping

PROXY_CONTROLLED_HEADERS: Final[frozenset[str]] = frozenset(
    {
        "connection",
        "content-length",
        "host",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailer",
        "transfer-encoding",
        "upgrade",
    }
)

def sanitize_request_headers(headers: Mapping[str, str]) -> dict[str, str]:
    """Remove proxy-controlled headers before forwarding to the relay API.

    :param headers: Incoming HTTP headers.
    :returns: Headers safe to forward to the internal API relay.
    """
    return {
        str(header_name): str(header_value)
        for header_name, header_value in headers.items()
        if str(header_name).lower() not in PROXY_CONTROLLED_HEADERS
    }