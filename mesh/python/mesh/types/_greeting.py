from pydantic import BaseModel
from .__common import NodeId, VersionId


class Greeting(BaseModel):
    node_id: NodeId
    name: str
    version: VersionId
