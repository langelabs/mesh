"""Unit tests for mesh helper utilities."""

from mesh_service.utils.headers import sanitize_request_headers
from mesh_service.utils.name import extract_mesh_name, is_valid_relay_name


def test_is_valid_relay_name_accepts_dns_label_safe_names() -> None:
    """Assert relay names accept the public DNS-label-safe contract."""
    assert is_valid_relay_name("demo-1") is True


def test_is_valid_relay_name_rejects_nested_or_empty_names() -> None:
    """Assert relay names reject empty, dotted, or whitespace-only values."""
    assert is_valid_relay_name("") is False
    assert is_valid_relay_name("a.b") is False
    assert is_valid_relay_name("   ") is False


def test_extract_mesh_name_accepts_single_label_wildcard_host() -> None:
    """Assert single-label mesh hosts produce the relay name."""
    assert extract_mesh_name("demo.mesh.lange-labs.com", "mesh.lange-labs.com") == "demo"


def test_extract_mesh_name_rejects_root_domain() -> None:
    """Assert the bare mesh domain is not a valid named relay host."""
    assert extract_mesh_name("mesh.lange-labs.com", "mesh.lange-labs.com") is None


def test_extract_mesh_name_rejects_multi_label_wildcard_host() -> None:
    """Assert wildcard matching accepts only one label before the base domain."""
    assert extract_mesh_name("a.b.mesh.lange-labs.com", "mesh.lange-labs.com") is None


def test_extract_mesh_name_ignores_host_port() -> None:
    """Assert local or proxied hosts may include a port suffix."""
    assert extract_mesh_name("demo.mesh.lange-labs.com:8084", "mesh.lange-labs.com") == "demo"


def test_sanitize_request_headers_drops_proxy_headers() -> None:
    """Assert proxy-owned headers are removed while app headers are preserved."""
    headers = sanitize_request_headers(
        {
            "Host": "demo.mesh.lange-labs.com",
            "Connection": "keep-alive",
            "Content-Length": "4",
            "Transfer-Encoding": "chunked",
            "Upgrade": "websocket",
            "Authorization": "Bearer token",
            "Content-Type": "application/json",
        }
    )

    assert headers == {
        "Authorization": "Bearer token",
        "Content-Type": "application/json",
    }
