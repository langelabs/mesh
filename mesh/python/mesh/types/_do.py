from pydantic import BaseModel
from .__common import BaseTypes, NodeId, CmdId

class Do(BaseModel):
    node: NodeId
    id: CmdId
    inputs: list[BaseTypes]

