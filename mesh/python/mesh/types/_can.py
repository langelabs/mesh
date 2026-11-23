from pydantic import BaseModel
from .__common import BaseTypes, NodeId, CmdId


class CanParameter(BaseModel):
    name: str
    type: BaseTypes
    description: str


class Can(BaseModel):
    node: NodeId
    name: str
    description: str
    id: CmdId
    input: list[CanParameter]
    output: list[CanParameter]
