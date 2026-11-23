from .__base import MeshMsg, MeshMsgPayload
from ..types import Greeting
from typing import Literal


class MeshMsgHello(MeshMsg):
    class Payload(MeshMsgPayload):
        greeting: Greeting

    msg: Literal["hello"] = "hello"
    payload: Payload

class MeshMsgHelloAck(MeshMsg):
    class Payload(MeshMsgPayload):
        greeting: Greeting

    msg: Literal["-hello"] = "-hello"
    payload: Payload