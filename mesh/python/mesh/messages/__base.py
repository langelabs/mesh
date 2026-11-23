from typing import Literal, Optional

from pydantic import BaseModel
from abc import ABC
from ..types import NodeId, Error

class MeshMsgPayload(BaseModel, ABC):
    error:Optional[Error] = None

class MeshMsgMeta(BaseModel):
    version: int
    node_from: NodeId
    node_to: NodeId
    hops: list[NodeId]

class MeshMsg(BaseModel, ABC):
    class Payload(MeshMsgPayload):
        ...

    meta: MeshMsgMeta

    # message
    msg: Literal[
        "hello", "-hello",
        "friends", "-friends",
        "can", "-can",
        "do", "-do"
    ]
    payload: Payload
