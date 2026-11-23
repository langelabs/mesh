from typing import Literal

from .__base import MeshMsg
from ..types import Can

class MeshMsgCan(MeshMsg):
    msg: Literal["can"] = "can"

class MeshMsgCanAck(MeshMsg):
    class Payload(MeshMsg.Payload):
        can: list[Can]

    msg: Literal["-can"] = "-can"
    payload: Payload
