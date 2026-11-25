from .connections import BaseConnection, HandlerProtocol
from .messages import (
    MeshMsg,
    MeshMsgCan,
    MeshMsgCanAck,
    MeshMsgDo,
    MeshMsgDoAck,
    MeshMsgFriends,
    MeshMsgFriendsAck,
    MeshMsgHello,
    MeshMsgHelloAck,
    MeshMsgMeta,
)
from .tool_group import MeshToolGroup
from .types import Error, Friend, Greeting, NodeId, VersionId


class MeshRouter(MeshToolGroup, HandlerProtocol):
    """Track a mesh node's local capabilities, peers, and connections."""

    async def hande_message(self, msg: MeshMsg) -> MeshMsg | MeshMsg.Payload:
        """Dispatch a message to the appropriate Mesh handler.

        :param msg: Incoming request or acknowledgement.
        :returns: A reply envelope for a request or the payload of an acknowledgement.
        :raises NotImplementedError: If the message type has no handler.
        """
        # hello
        if isinstance(msg, MeshMsgHello):
            return await self._handle_hello_request(msg)
        elif isinstance(msg, MeshMsgHelloAck):
            return await self._handle_hello_ack(msg)

        # can
        elif isinstance(msg, MeshMsgCan):
            return await self._handle_can_request(msg)
        elif isinstance(msg, MeshMsgCanAck):
            return await self._handle_can_ack(msg)

        # do
        elif isinstance(msg, MeshMsgDo):
            return await self._handle_do_request(msg)
        elif isinstance(msg, MeshMsgDoAck):
            return await self._handle_do_ack(msg)

        # friends
        elif isinstance(msg, MeshMsgFriends):
            return await self._handle_friends_request(msg)
        elif isinstance(msg, MeshMsgFriendsAck):
            return await self._handle_friends_ack(msg)

        raise NotImplementedError("Message type not implemented.")


    def __init__(self) -> None:
        """Initialize local tools, a routing table, and peer connections."""
        super().__init__()

        # self meta information
        self._version: VersionId = 0
        self._name: str = f"NODE:{self._id}"

        # known friends routing table
        self._friends: dict[NodeId, Friend] = {}

        # actual connections
        self._connections: dict[NodeId, BaseConnection] = {}

    def get_greeting(self) -> Greeting:
        """Return this node's current identity and protocol version.

        :returns: The greeting advertised to peers.
        """
        return Greeting(node_id=self._id, name=self._name, version=self._version)

    def __get_msg_meta(self, to: NodeId) -> MeshMsgMeta:
        """Build message metadata for an outbound reply.

        :param to: Destination node ID.
        :returns: Metadata identifying this node as the sender and first hop.
        """
        return MeshMsgMeta(
            version=self._version, node_from=self._id, node_to=to, hops=[self._id]
        )

    def __merge_friends(self, new_friends: list[Friend]) -> None:
        """Merge peer routes into the local routing table.

        :param new_friends: Peer routes learned from another node.
        """
        for new_friend in new_friends:
            if new_friend.id == self._id:
                continue

            current = self._friends.get(new_friend.id)
            if current is None:
                self._friends[new_friend.id] = new_friend.model_copy(deep=True)
                continue

            primary, alternate = current, new_friend
            if new_friend.distance < current.distance:
                primary, alternate = new_friend, current

            detours = dict.fromkeys(
                [*primary.detours, alternate.via, *alternate.detours]
            )
            detours.pop(primary.via, None)
            self._friends[new_friend.id] = primary.model_copy(
                update={"detours": list(detours)}
            )

    def __merge_greeting(self, greeting: Greeting) -> None:
        """Record a directly reachable peer from a hello message.

        :param greeting: Identity and version advertised by the peer.
        """
        self.__merge_friends(
            [
                Friend(
                    id=greeting.node_id,
                    name=greeting.name,
                    version=greeting.version,
                    distance=1,
                    via=greeting.node_id,
                    detours=[],
                )
            ]
        )

    async def _handle_can_request(self, msg: MeshMsgCan) -> MeshMsgCanAck:
        """Advertise this node's registered capabilities to the requester.

        :param msg: Capability discovery request.
        :returns: A reply containing the capability descriptions.
        """
        return MeshMsgCanAck(
            meta=self.__get_msg_meta(msg.meta.node_from),
            payload=MeshMsgCanAck.Payload(
                can=[capability for capability, _ in self._capabilities.values()]
            ),
        )

    async def _handle_do_request(self, msg: MeshMsgDo) -> MeshMsgDoAck:
        """Await the registered capability with the supplied positional inputs.

        :param msg: Invocation request.
        :returns: A result reply, empty outputs for ``None``, or an error reply
            with code 404 for an unknown capability or 500 for a failure.
        """
        registered = self._capabilities.get(msg.payload.id)
        if registered is None:
            payload = MeshMsgDoAck.Payload(
                outputs=[], error=Error(code=404, message="Unknown capability")
            )
        else:
            _, func = registered
            try:
                result = await func(*msg.payload.input)
                payload = MeshMsgDoAck.Payload.model_validate(
                    {"outputs": [] if result is None else [result]}
                )
            except Exception:
                payload = MeshMsgDoAck.Payload(
                    outputs=[],
                    error=Error(code=500, message="Capability invocation failed"),
                )

        return MeshMsgDoAck(
            meta=self.__get_msg_meta(msg.meta.node_from),
            payload=payload,
        )

    async def _handle_friends_request(self, msg: MeshMsgFriends) -> MeshMsgFriendsAck:
        """Advertise known peers within the distance requested by the sender.

        :param msg: Peer discovery request.
        :returns: A reply with peers reachable via this node.
        """
        requester = msg.meta.node_from
        friends = [
            friend.model_copy(
                update={"via": self._id, "distance": friend.distance + 1, "detours": []}
            )
            for friend in self._friends.values()
            if friend.distance < msg.payload.max_distance and friend.via != requester
        ]
        return MeshMsgFriendsAck(
            meta=self.__get_msg_meta(requester),
            payload=MeshMsgFriendsAck.Payload(friends=friends),
        )

    async def _handle_hello_request(self, msg: MeshMsgHello) -> MeshMsgHelloAck:
        """Respond to a greeting with this node's identity.

        :param msg: Greeting request.
        :returns: A reply containing this node's greeting.
        """
        self.__merge_greeting(msg.payload.greeting)
        return MeshMsgHelloAck(
            meta=self.__get_msg_meta(msg.meta.node_from),
            payload=MeshMsgHelloAck.Payload(greeting=self.get_greeting()),
        )

    async def _handle_can_ack(self, msg: MeshMsgCanAck) -> MeshMsgCanAck.Payload:
        """Return the capability discovery reply to the caller.

        :param msg: Capability discovery reply.
        :returns: The advertised capabilities.
        """
        return msg.payload

    async def _handle_do_ack(self, msg: MeshMsgDoAck) -> MeshMsgDoAck.Payload:
        """Return the capability invocation reply to the caller.

        :param msg: Capability invocation reply.
        :returns: The invocation result payload.
        """
        return msg.payload

    async def _handle_friends_ack(
            self, msg: MeshMsgFriendsAck
    ) -> MeshMsgFriendsAck.Payload:
        """Learn peer routes from a discovery reply.

        :param msg: Peer discovery reply.
        :returns: The peer discovery payload.
        """
        self.__merge_friends(msg.payload.friends)
        return msg.payload

    async def _handle_hello_ack(self, msg: MeshMsgHelloAck) -> MeshMsgHelloAck.Payload:
        """Record the identity of the peer that answered a hello request.

        :param msg: Greeting reply.
        :returns: The peer greeting payload.
        """
        self.__merge_greeting(msg.payload.greeting)
        return msg.payload
