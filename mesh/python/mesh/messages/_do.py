from typing import Literal

from ..types import BaseTypes
from ..types.__common import CmdId
from .__base import MeshMsg


class MeshMsgDo(MeshMsg):
    class Payload(MeshMsg.Payload):
        id: CmdId
        input: list[BaseTypes]

    msg: Literal["do"] = "do"
    payload: Payload


class MeshMsgDoAck(MeshMsg):
    class Payload(MeshMsg.Payload):
        outputs: list[BaseTypes]

    msg: Literal["-do"] = "-do"
    payload: Payload
