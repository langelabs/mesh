from typing import Literal

from pydantic import BaseModel


class WorkerView(BaseModel):
    """Serializable view of a connected mesh worker."""

    name: str
    ip_address: str | None
    timeout: float
    status: Literal["ready", "pending", "failed"]
