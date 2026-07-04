"""Helpers for serializing mesh websocket messages."""

from typing import Any

from lange.contracts.mesh import MeshMessage
from pydantic import BaseModel


def dump_mesh_message(message: MeshMessage) -> dict[str, Any]:
    """Serialize one mesh message using aliases for nested payload contracts.

    :param message: Mesh message to serialize for JSON transport.
    :returns: JSON-compatible mesh message payload.
    """
    payload = message.model_dump(mode="json", by_alias=True)
    if isinstance(message.data, BaseModel):
        payload["data"] = message.data.model_dump(mode="json", by_alias=True)
    return payload
