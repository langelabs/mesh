#pragma once

#include <lange_mesh/types.hpp>

#include <optional>
#include <string_view>

namespace lange_mesh {

/// The sender, destination, version, and path shared by all messages.
struct MessageMeta {
    VersionId version{};
    NodeId node_from;
    NodeId node_to;
    std::vector<NodeId> hops;
};

/// A greeting request or acknowledgement carrying the advertising node's identity.
template <bool IsAcknowledgement>
struct GreetingPayload {
    static constexpr std::string_view kind = IsAcknowledgement ? "-hello" : "hello";
    Greeting greeting;
    std::optional<MeshError> error;
};

using HelloPayload = GreetingPayload<false>;
using HelloAckPayload = GreetingPayload<true>;

/// A request for routes within a distance limit.
struct FriendsPayload {
    static constexpr std::string_view kind = "friends";
    std::int64_t max_distance{};
    std::optional<MeshError> error;
};

/// The routes advertised by a responding node.
struct FriendsAckPayload {
    static constexpr std::string_view kind = "-friends";
    std::vector<Friend> friends;
    std::optional<MeshError> error;
};

/// A request for a node's advertised capabilities.
struct CanPayload {
    static constexpr std::string_view kind = "can";
    std::optional<MeshError> error;
};

/// The capabilities advertised by a responding node.
struct CanAckPayload {
    static constexpr std::string_view kind = "-can";
    std::vector<Capability> can;
    std::optional<MeshError> error;
};

/// A command ID and its positional inputs.
struct DoPayload {
    static constexpr std::string_view kind = "do";
    CmdId id;
    std::vector<BaseValue> input;
    std::optional<MeshError> error;
};

/// The outputs or error of a capability invocation.
struct DoAckPayload {
    static constexpr std::string_view kind = "-do";
    std::vector<BaseValue> outputs;
    std::optional<MeshError> error;
};

/// All request and acknowledgement payloads accepted by a router.
using Payload = std::variant<HelloPayload, HelloAckPayload, FriendsPayload, FriendsAckPayload,
                             CanPayload, CanAckPayload, DoPayload, DoAckPayload>;

/// The common Mesh envelope. The concrete payload determines its wire name.
struct Message {
    MessageMeta meta;
    Payload payload;
};

/// Decode one Mesh JSON message. Throws std::invalid_argument for malformed wire data.
Message parse_message(std::string_view data);

/// Encode a Mesh message as JSON. Throws std::invalid_argument for invalid values or text.
std::string encode_message(const Message& message);

} // namespace lange_mesh
