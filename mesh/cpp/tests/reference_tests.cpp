#include <lange_mesh/router.hpp>

#include <fstream>
#include <iostream>
#include <limits>
#include <nlohmann/json.hpp>
#include <stdexcept>
#include <utility>

using namespace lange_mesh;

/// Fail the test with a diagnostic in all build configurations.
void require(bool condition, const char* message) {
    if (!condition) {
        throw std::runtime_error(message);
    }
}

/// Require the decoder to reject malformed wire data.
void require_invalid(std::string_view wire) {
    try {
        parse_message(wire);
    } catch (const std::invalid_argument&) {
        return;
    }
    throw std::runtime_error("accepted invalid message: " + std::string(wire));
}

/// Check JSON decoding and encoding against the cross-language fixtures.
void test_messages(const std::string& fixtures) {
    using nlohmann::json;
    std::ifstream valid(fixtures + "/messages-valid.jsonl");
    require(valid.is_open(), "cannot open valid fixtures");
    std::string line;
    while (std::getline(valid, line)) {
        auto expected = json::parse(line);
        if (!expected.at("payload").contains("error")) {
            expected["payload"]["error"] = nullptr;
        }
        if (json::parse(encode_message(parse_message(line))).dump() != expected.dump()) {
            throw std::runtime_error("round trip changed: " + line);
        }
    }

    std::ifstream invalid(fixtures + "/messages-invalid.jsonl");
    require(invalid.is_open(), "cannot open invalid fixtures");
    while (std::getline(invalid, line)) {
        require_invalid(line);
    }
    const auto wire = encode_message(Message{{}, CanPayload{}});
    require_invalid(wire + '\0' + "{}");
}

/// Deliver a typed message from a peer and check any reply destination.
RouteOutcome dispatch(Router& router, Payload payload) {
    auto outcome = router.handle_message(Message{{1, "peer", "local", {"peer"}}, std::move(payload)});
    if (const auto* reply = std::get_if<Message>(&outcome)) {
        const auto& meta = reply->meta;
        require(meta.version == 7 && meta.node_from == "local" && meta.node_to == "peer" &&
                meta.hops == std::vector<NodeId>{"local"}, "wrong reply metadata");
    }
    return outcome;
}

/// Check greeting and friend discovery state transitions.
void test_gossip() {
    Router router({"local", "Local", 7});
    const auto hello = std::get<Message>(dispatch(router, HelloPayload{{"peer", "Peer", 1}, {}}));
    require(std::get<HelloAckPayload>(hello.payload).greeting.name == "Local", "wrong greeting");
    auto ack = std::get<Acknowledgement>(
        dispatch(router, HelloAckPayload{{"direct", "Direct", 1}, {}}));
    require(std::holds_alternative<HelloAckPayload>(ack), "missing greeting acknowledgment");
    for (const auto* id : {"peer", "direct"}) {
        const auto friend_route = router.friend_route(id);
        require(friend_route && friend_route->via == id && friend_route->distance == 1,
                "missing direct route");
    }

    ack = std::get<Acknowledgement>(dispatch(router, FriendsAckPayload{{
        {"near", "Near", 1, 3, "peer", {"backup"}},
        {"back", "Back", 1, 2, "peer", {}},
        {"local", "Local", 7, 1, "peer", {}},
    }, {}}));
    require(std::get<FriendsAckPayload>(ack).friends.size() == 3, "missing friends acknowledgment");
    dispatch(router, FriendsAckPayload{{
        {"near", "Near", 1, 2, "other", {"backup", "other"}},
        {"back", "Back", 1, 2, "other", {}},
        {"far", "Far", 1, 3, "other", {}},
    }, {}});

    auto near = router.friend_route("near");
    require(near && near->distance == 2 && near->via == "other" &&
            near->detours == std::vector<NodeId>{"backup", "peer"}, "wrong shortest route");
    near->detours.clear();
    require(router.friend_route("near")->detours.size() == 2, "friend snapshot changed router state");
    const auto back = router.friend_route("back");
    require(back && back->via == "peer" && back->detours == std::vector<NodeId>{"other"},
            "wrong tied route");
    require(!router.friend_route("local"), "learned a route to local node");

    const auto reply = std::get<Message>(dispatch(router, FriendsPayload{3, {}}));
    const auto& friends = std::get<FriendsAckPayload>(reply.payload).friends;
    require(friends.size() == 2 && friends[0].id == "direct" && friends[1].id == "near" &&
            friends[1].distance == 3 && friends[1].via == "local" && friends[1].detours.empty(),
            "wrong advertised routes");
}

/// Check tool discovery, output shapes, and protocol errors.
void test_tools() {
    Router router({"local", "Local", 7});
    ToolGroup group("source");
    const Capability echo{"source", "echo", "Echo", "Echo a value", {}, {}};
    group.add_to_mesh(echo, [](const auto& input) -> ToolResult { return input.at(0); });
    router.tools().add_tool_group(group);
    group.add_to_mesh(echo, [](const auto&) -> ToolResult { return std::nullopt; });
    router.tools().add_to_mesh({"", "empty", "", "", {}, {}},
                               [](const auto&) -> ToolResult { return std::nullopt; });
    router.tools().add_to_mesh({"", "fail", "", "", {}, {}}, [](const auto&) -> ToolResult {
        throw std::runtime_error("private details");
    });
    router.tools().add_to_mesh({"", "invalid", "", "", {}, {}}, [](const auto&) -> ToolResult {
        return std::numeric_limits<double>::infinity();
    });

    auto reply = std::get<Message>(dispatch(router, CanPayload{}));
    const auto can = std::get<CanAckPayload>(reply.payload);
    require(can.can.size() == 4 && can.can[0].id == "echo" && can.can[0].node == "local",
            "wrong capability listing");
    require(std::holds_alternative<CanAckPayload>(std::get<Acknowledgement>(dispatch(router, can))),
            "missing capability acknowledgment");

    const auto input = BaseValue{AtomicArray{std::string("text"), true}};
    for (const auto& [id, code] : std::vector<std::pair<CmdId, int>>{
             {"echo", 0}, {"empty", 0}, {"missing", 404}, {"fail", 500}, {"invalid", 500}}) {
        reply = std::get<Message>(dispatch(router, DoPayload{id, {input}, {}}));
        const auto result = std::get<DoAckPayload>(reply.payload);
        require(result.outputs == (id == "echo" ? std::vector<BaseValue>{input} :
                                                    std::vector<BaseValue>{}),
                "wrong tool output");
        if (code == 0) {
            require(!result.error, "unexpected tool error");
        } else {
            require(result.error && result.error->code == code, "wrong tool error code");
            require(result.error->message == (code == 404 ? "Unknown capability" :
                                                            "Capability invocation failed"),
                    "wrong tool error message");
        }
        require(std::holds_alternative<DoAckPayload>(
                    std::get<Acknowledgement>(dispatch(router, result))),
                "missing invocation acknowledgment");
    }
}

/// Run the wire and router tests using the supplied fixture directory.
int main(int argc, char** argv) {
    try {
        require(argc == 2, "expected fixture directory argument");
        test_messages(argv[1]);
        test_gossip();
        test_tools();
    } catch (const std::exception& error) {
        std::cerr << error.what() << '\n';
        return 1;
    }
}
