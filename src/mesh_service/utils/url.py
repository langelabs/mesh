from urllib.parse import quote

def build_upstream_url(
    relay_base_url: str,
    name: str,
    path: str,
    query_string: str,
) -> str:
    """Build the internal API relay URL for one incoming mesh request.

    :param relay_base_url: Internal API relay endpoint base URL.
    :param name: Relay key extracted from the public hostname.
    :param path: Incoming request path without a leading slash.
    :param query_string: Raw incoming query string.
    :returns: Absolute internal relay URL.
    """
    normalized_base_url = relay_base_url.rstrip("/")
    quoted_key = quote(name, safe="")
    normalized_path = path.lstrip("/")
    if normalized_path:
        quoted_path = "/".join(quote(part, safe="") for part in normalized_path.split("/"))
        url = f"{normalized_base_url}/{quoted_key}/{quoted_path}"
    else:
        url = f"{normalized_base_url}/{quoted_key}"
    if query_string:
        url = f"{url}?{query_string}"
    return url