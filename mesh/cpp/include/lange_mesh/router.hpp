#pragma once

#include <lange_mesh/tool_group.hpp>

namespace lange_mesh {

/// A typed acknowledgement delivered to the local caller.
using Acknowledgement = std::variant<HelloAckPayload, FriendsAckPayload, CanAckPayload, DoAckPayload>;

/// A reply message to send or an acknowledgement to deliver locally.
using RouteOutcome = std::variant<Message, Acknowledgement>;

/// A node's identity, advertised capabilities, and known peer routes.
class Router {
public:
    /// Create a local router using the supplied identity.
    explicit Router(Greeting identity);

    /// Access the local capability group.
    ToolGroup& tools();

    /// Return a snapshot of a known peer route.
    std::optional<Friend> friend_route(const NodeId& id) const;

    /// Dispatch an inbound message already delivered to this node.
    RouteOutcome handle_message(Message message);

private:
    /// Learn the direct route advertised in either greeting direction.
    void merge_greeting(const Greeting& greeting);

    /// Keep the shortest route and record distinct alternate next hops.
    void merge_friends(const std::vector<Friend>& incoming);

    Greeting identity_;
    ToolGroup tools_;
    std::vector<Friend> friends_;
};

} // namespace lange_mesh
