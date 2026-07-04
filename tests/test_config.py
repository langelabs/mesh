"""Tests for mesh service runtime configuration."""

from mesh_service.config import get_settings


def test_get_settings_reads_environment_overrides(monkeypatch) -> None:
    """Assert mesh runtime settings can be configured by environment variables."""
    monkeypatch.setenv("MESH_BASE_DOMAIN", "mesh.example.com")
    monkeypatch.setenv("MESH_WORKER_SECRET", "secret-token")

    settings = get_settings()

    assert settings.mesh_base_domain == "mesh.example.com"
    assert settings.worker_secret == "secret-token"


def test_get_settings_defaults_optional_worker_secret(monkeypatch) -> None:
    """Assert worker authentication is disabled when no secret is configured."""
    monkeypatch.setenv("MESH_BASE_DOMAIN", "mesh.example.com")
    monkeypatch.delenv("MESH_WORKER_SECRET", raising=False)

    settings = get_settings()

    assert settings.mesh_base_domain == "mesh.example.com"
    assert settings.worker_secret is None
