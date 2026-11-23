from .__base import MeshMsg, MeshMsgPayload
from ..types import Friend
from typing import Literal


class MeshMsgFriends(MeshMsg):
    class Payload(MeshMsgPayload):
        max_distance: int

    msg:Literal["friends"] = "friends"
    payload:Payload

class MeshMsgFriendsAck(MeshMsg):
    class Payload(MeshMsgPayload):
        friends: list[Friend]

    msg:Literal["-friends"] = "-friends"
    payload: Payload