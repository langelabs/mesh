from pydantic import BaseModel
from .__common import NodeId, VersionId

class Friend(BaseModel):
    id: NodeId
    name: str
    version: VersionId
    distance: int
    via: NodeId
    detours: list[NodeId]
