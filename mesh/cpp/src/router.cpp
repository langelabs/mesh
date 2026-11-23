#include <lange_mesh/router.hpp>

#include <algorithm>
#include <type_traits>
#include <unordered_set>
#include <utility>

namespace lange_mesh {

Router::Router(Greeting identity)
    : identity_(std::move(identity)), tools_(identity_.node_id) {}

ToolGroup& Router::tools() {
    return tools_;
}

std::optional<Friend> Router::friend_route(const NodeId& id) const {
    const auto found = std::find_if(friends_.begin(), friends_.end(), [&](const Friend& route) {
        return route.id == id;
    });
    if (found == friends_.end()) {
        return std::nullopt;
    }
    return *found;
}

RouteOutcome Router::handle_message(Message message) {
    const auto reply = [&](Payload payload) {
        return Message{
            {identity_.version, identity_.node_id, message.meta.node_from, {identity_.node_id}},
            std::move(payload),
        };
    };

    return std::visit([&](auto& payload) -> RouteOutcome {
        using Type = std::decay_t<decltype(payload)>;
        if constexpr (std::is_same_v<Type, HelloPayload>) {
            merge_greeting(payload.greeting);
            return reply(HelloAckPayload{identity_, {}});
        } else if constexpr (std::is_same_v<Type, HelloAckPayload>) {
            merge_greeting(payload.greeting);
            return Acknowledgement{std::move(payload)};
        } else if constexpr (std::is_same_v<Type, FriendsPayload>) {
            FriendsAckPayload result;
            for (const auto& route : friends_) {
                if (route.distance < payload.max_distance && route.via != message.meta.node_from) {
                    result.friends.push_back({
                        route.id, route.name, route.version, route.distance + 1, identity_.node_id, {},
                    });
                }
            }
            return reply(std::move(result));
        } else if constexpr (std::is_same_v<Type, FriendsAckPayload>) {
            merge_friends(payload.friends);
            return Acknowledgement{std::move(payload)};
        } else if constexpr (std::is_same_v<Type, CanPayload>) {
            return reply(CanAckPayload{tools_.capabilities(), {}});
        } else if constexpr (std::is_same_v<Type, DoPayload>) {
            return reply(tools_.invoke(payload.id, payload.input));
        } else {
            return Acknowledgement{std::move(payload)};
        }
    }, message.payload);
}

void Router::merge_greeting(const Greeting& greeting) {
    merge_friends({{greeting.node_id, greeting.name, greeting.version, 1, greeting.node_id, {}}});
}

void Router::merge_friends(const std::vector<Friend>& incoming) {
    for (auto alternate : incoming) {
        if (alternate.id == identity_.node_id) {
            continue;
        }
        const auto found = std::find_if(friends_.begin(), friends_.end(), [&](const Friend& route) {
            return route.id == alternate.id;
        });
        if (found == friends_.end()) {
            friends_.push_back(std::move(alternate));
            continue;
        }

        auto primary = *found;
        if (alternate.distance < primary.distance) {
            std::swap(primary, alternate);
        }
        std::vector<NodeId> detours;
        std::unordered_set<NodeId> seen{primary.via};
        const auto record = [&](const NodeId& via) {
            if (seen.insert(via).second) {
                detours.push_back(via);
            }
        };
        std::for_each(primary.detours.begin(), primary.detours.end(), record);
        record(alternate.via);
        std::for_each(alternate.detours.begin(), alternate.detours.end(), record);
        primary.detours = std::move(detours);
        *found = std::move(primary);
    }
}

} // namespace lange_mesh
