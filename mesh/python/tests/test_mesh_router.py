"""Test tool groups and mesh message handlers."""

from __future__ import annotations

import asyncio
from typing import Annotated

import pytest

from mesh.messages import (
    MeshMsgCan,
    MeshMsgDo,
    MeshMsgDoAck,
    MeshMsgFriends,
    MeshMsgFriendsAck,
    MeshMsgHello,
    MeshMsgMeta,
)
from mesh.router import MeshRouter
from mesh.tool_group import MeshToolGroup
from mesh.types import CanParameter, Friend, Greeting


@pytest.fixture
def can_request() -> MeshMsgCan:
    """Build a discovery request from a peer.

    :returns: A capability discovery message.
    """
    return MeshMsgCan(
        meta=MeshMsgMeta(version=0, node_from="peer", node_to="router", hops=["peer"]),
        payload=MeshMsgCan.Payload(),
    )


def test_add_to_mesh_advertises_function_metadata(can_request: MeshMsgCan) -> None:
    """Read capability metadata from a function and return it to the peer.

    :param can_request: Discovery request from the peer.
    """
    router = MeshRouter()

    async def greet(
        names: Annotated[list[str], "Names to greet"], punctuation: str = "!"
    ) -> Annotated[str, "Greeting text"]:
        """Greet a list of names.

        :param names: Names to greet.
        :param punctuation: Punctuation to append.
        :returns: The greeting.
        """
        return f"Hello {', '.join(names)}{punctuation}"

    assert asyncio.run(router._handle_can_request(can_request)).payload.can == []
    router.add_to_mesh(greet)

    reply = asyncio.run(router._handle_can_request(can_request))
    (capability,) = reply.payload.can
    assert reply.msg == "-can"
    assert reply.meta.node_to == can_request.meta.node_from
    assert capability.node == reply.meta.node_from
    assert capability.id == f"{greet.__module__}.{greet.__qualname__}"
    assert capability.name == "greet"
    assert capability.description.startswith("Greet a list of names.")
    assert capability.input == [
        CanParameter(name="names", type="list[str]", description="Names to greet"),
        CanParameter(name="punctuation", type="str", description=""),
    ]
    assert capability.output == [
        CanParameter(name="return", type="str", description="Greeting text")
    ]


def test_meshed_registers_and_preserves_the_callable(can_request: MeshMsgCan) -> None:
    """Register a callable through the decorator and preserve direct calls.

    :param can_request: Discovery request from the peer.
    """
    router = MeshRouter()
    seen: list[int] = []

    async def record(value: int) -> None:
        """Keep the value passed by the caller.

        :param value: Value to record.
        """
        seen.append(value)

    decorated = router.meshed(record)
    assert decorated is record
    asyncio.run(decorated(42))
    assert seen == [42]

    (capability,) = asyncio.run(router._handle_can_request(can_request)).payload.can
    assert capability.name == "record"
    assert capability.output == []


def test_add_to_mesh_rejects_synchronous_functions() -> None:
    """Reject a synchronous callable during registration."""

    def synchronous() -> int:
        """Return a value synchronously.

        :returns: A sample integer.
        """
        return 42

    with pytest.raises(TypeError, match="async"):
        MeshRouter().add_to_mesh(synchronous)  # type: ignore[arg-type]


def peer_message_meta(sender: MeshRouter, recipient: MeshRouter) -> MeshMsgMeta:
    """Build metadata for a direct message between two routers.

    :param sender: Router sending the message.
    :param recipient: Router receiving the message.
    :returns: Message metadata for the direct hop.
    """
    return MeshMsgMeta(
        version=0, node_from=sender._id, node_to=recipient._id, hops=[sender._id]
    )


def test_add_tool_group_advertises_nested_tools_on_the_receiving_router() -> None:
    """Keep merged tools callable and preserve the source group's ownership."""
    leaf = MeshToolGroup()
    parent = MeshToolGroup()
    router = MeshRouter()
    peer = MeshRouter()

    @leaf.meshed
    async def greet() -> str:
        """Return a greeting.

        :returns: Greeting text.
        """
        return "hello"

    parent.add_tool_group(leaf)
    router.add_tool_group(parent)
    request = MeshMsgCan(
        meta=peer_message_meta(peer, router), payload=MeshMsgCan.Payload()
    )
    reply = asyncio.run(router._handle_can_request(request))
    (capability,) = reply.payload.can
    assert len({leaf._id, parent._id, router._id, peer._id}) == 4
    assert capability.node == router._id
    original, func = leaf._capabilities[capability.id]
    assert original.node == leaf._id
    assert router._capabilities[capability.id][1] is func is greet


@pytest.mark.parametrize("result, outputs", [(None, []), ([1, 2], [[1, 2]])])
def test_do_request_awaits_registered_tool(
    result: list[int] | None, outputs: list[list[int]]
) -> None:
    """Pass positional inputs and encode a single result, including a list.

    :param result: Result produced by the registered tool.
    :param outputs: Expected outputs in the acknowledgement payload.
    """
    router = MeshRouter()
    peer = MeshRouter()

    @router.meshed
    async def invoke(value: str) -> list[int] | None:
        """Return the test result after checking the argument.

        :param value: Argument sent in the request.
        :returns: The test result.
        """
        assert value == "argument"
        return result

    request = MeshMsgDo(
        meta=peer_message_meta(peer, router),
        payload=MeshMsgDo.Payload(
            id=f"{invoke.__module__}.{invoke.__qualname__}", input=["argument"]
        ),
    )
    reply = asyncio.run(router.hande_message(request))
    assert isinstance(reply, MeshMsgDoAck)
    assert reply.meta.node_to == peer._id
    payload = asyncio.run(peer.hande_message(reply))
    assert isinstance(payload, MeshMsgDoAck.Payload)
    assert payload.outputs == outputs
    assert reply.payload.error is None


def test_do_request_reports_unknown_capability_in_payload() -> None:
    """Return an error acknowledgement when the requested ID is unregistered."""
    peer, router = MeshRouter(), MeshRouter()
    request = MeshMsgDo(
        meta=peer_message_meta(peer, router),
        payload=MeshMsgDo.Payload(id="unknown", input=[]),
    )

    reply = asyncio.run(router._handle_do_request(request))
    assert reply.meta.node_to == peer._id
    assert reply.payload.outputs == []
    assert reply.payload.error is not None
    assert reply.payload.error.code == 404


def test_do_request_reports_failure_without_exposing_exception() -> None:
    """Return an invocation error without exposing internal exception details."""
    peer, router = MeshRouter(), MeshRouter()

    @router.meshed
    async def fail() -> None:
        """Raise an exception whose details should stay local.

        :raises RuntimeError: Always, to simulate a tool failure.
        """
        raise RuntimeError("private details")

    request = MeshMsgDo(
        meta=peer_message_meta(peer, router),
        payload=MeshMsgDo.Payload(
            id=f"{fail.__module__}.{fail.__qualname__}", input=[]
        ),
    )

    reply = asyncio.run(router._handle_do_request(request))
    payload = asyncio.run(peer._handle_do_ack(reply))
    assert payload.outputs == []
    assert payload.error is not None
    assert payload.error.code == 500
    assert "private details" not in payload.error.message


def test_can_ack_returns_discovery_payload(can_request: MeshMsgCan) -> None:
    """Return the received capability descriptions to the caller.

    :param can_request: Discovery request used to produce an acknowledgement.
    """
    router = MeshRouter()
    reply = asyncio.run(router._handle_can_request(can_request))
    assert asyncio.run(router._handle_can_ack(reply)) is reply.payload


def test_hello_handlers_learn_direct_routes() -> None:
    """Introduce both nodes to each other during the greeting exchange."""
    sender, recipient = MeshRouter(), MeshRouter()
    request = MeshMsgHello(
        meta=peer_message_meta(sender, recipient),
        payload=MeshMsgHello.Payload(
            greeting=Greeting(node_id=sender._id, name="sender", version=0)
        ),
    )

    reply = asyncio.run(recipient._handle_hello_request(request))
    assert reply.meta.node_to == sender._id
    assert asyncio.run(sender._handle_hello_ack(reply)) is reply.payload
    assert recipient._friends[sender._id].name == "sender"
    assert recipient._friends[sender._id].distance == 1
    assert sender._friends[recipient._id].via == recipient._id
    assert sender._friends[recipient._id].distance == 1


def test_friends_ack_keeps_shorter_route_and_merges_every_peer() -> None:
    """Learn multiple destinations and retain an alternate next hop."""
    peer, other, router = MeshRouter(), MeshRouter(), MeshRouter()
    initial = MeshMsgFriendsAck(
        meta=peer_message_meta(peer, router),
        payload=MeshMsgFriendsAck.Payload(
            friends=[
                Friend(
                    id="a", name="A", version=0, distance=3, via=peer._id, detours=[]
                ),
                Friend(
                    id="b", name="B", version=0, distance=2, via=peer._id, detours=[]
                ),
            ]
        ),
    )
    shorter = MeshMsgFriendsAck(
        meta=peer_message_meta(other, router),
        payload=MeshMsgFriendsAck.Payload(
            friends=[
                Friend(
                    id="a", name="A", version=0, distance=2, via=other._id, detours=[]
                ),
            ]
        ),
    )

    assert asyncio.run(router._handle_friends_ack(initial)) is initial.payload
    asyncio.run(router._handle_friends_ack(shorter))
    assert router._friends["a"].via == other._id
    assert router._friends["a"].distance == 2
    assert router._friends["a"].detours == [peer._id]
    assert router._friends["b"].via == peer._id
    assert shorter.payload.friends[0].detours == []


def test_friends_request_preserves_local_routes() -> None:
    """Advertise reachable peers at the next hop without changing the table."""
    peer, requester, router = MeshRouter(), MeshRouter(), MeshRouter()
    learned = MeshMsgFriendsAck(
        meta=peer_message_meta(peer, router),
        payload=MeshMsgFriendsAck.Payload(
            friends=[
                Friend(
                    id="near",
                    name="Near",
                    version=0,
                    distance=2,
                    via=peer._id,
                    detours=[],
                ),
                Friend(
                    id="far",
                    name="Far",
                    version=0,
                    distance=3,
                    via=peer._id,
                    detours=[],
                ),
            ]
        ),
    )
    asyncio.run(router._handle_friends_ack(learned))
    request = MeshMsgFriends(
        meta=peer_message_meta(requester, router),
        payload=MeshMsgFriends.Payload(max_distance=3),
    )

    reply = asyncio.run(router._handle_friends_request(request))
    (friend,) = reply.payload.friends
    assert reply.meta.node_to == requester._id
    assert (friend.id, friend.distance, friend.via) == ("near", 3, router._id)
    assert router._friends["near"].distance == 2
    assert router._friends["near"].via == peer._id
