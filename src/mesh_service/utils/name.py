import re
from typing import Final

RELAY_NAME_PATTERN: Final[re.Pattern[str]] = re.compile(r"^[A-Za-z0-9-]+$")


def is_valid_relay_name(name: str) -> bool:
    """Return whether one mesh name can be used as a public DNS label.

    :param name: Relay name candidate.
    :returns: ``True`` when the name is non-empty and DNS-label-safe.
    """
    normalized_name = name.strip()
    return "." not in normalized_name and RELAY_NAME_PATTERN.fullmatch(normalized_name) is not None


def extract_mesh_name(host: str, base_domain: str) -> str | None:
    """Extract a single-label mesh name from a public host.

    :param host: Incoming HTTP host header value.
    :param base_domain: Expected mesh base domain, for example
        ``mesh.lange-labs.com``.
    :returns: Mesh relay name when the host is valid, otherwise ``None``.
    """
    normalized_host = host.split(":", 1)[0].strip().lower().rstrip(".")
    normalized_base_domain = base_domain.strip().lower().rstrip(".")
    suffix = f".{normalized_base_domain}"

    if not normalized_host.endswith(suffix):
        return None

    name = normalized_host[: -len(suffix)]
    if "." in name or not is_valid_relay_name(name):
        return None
    return name
