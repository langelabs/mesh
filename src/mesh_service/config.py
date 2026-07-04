"""Runtime configuration for the mesh relay service."""

import os

from pydantic import BaseModel


class Settings(BaseModel):
    """Runtime settings for the standalone mesh service."""

    mesh_base_domain: str
    mesh_public_scheme: str = "https"
    worker_secret: str | None = None


def get_settings() -> Settings:
    """Read mesh runtime settings from environment variables.

    :returns: Current mesh service settings.
    """
    return Settings(
        mesh_base_domain=os.getenv("MESH_BASE_DOMAIN", "mesh.lange-labs.com"),
        mesh_public_scheme=os.getenv("MESH_PUBLIC_SCHEME", "https"),
        worker_secret=os.getenv("MESH_WORKER_SECRET") or None,
    )
