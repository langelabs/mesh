#include <lange_mesh/messages.hpp>

#include <array>
#include <limits>
#include <nlohmann/json.hpp>
#include <stdexcept>
#include <type_traits>
#include <utility>

namespace lange_mesh {

using nlohmann::json;

namespace {

/// Decode a protocol integer without truncating a float or an oversized unsigned integer.
std::int64_t read_integer(const json& value) {
    if (value.is_number_unsigned()) {
        const auto number = value.get<std::uint64_t>();
        if (number <= static_cast<std::uint64_t>(std::numeric_limits<std::int64_t>::max())) {
            return static_cast<std::int64_t>(number);
        }
    } else if (value.is_number_integer()) {
        return value.get<std::int64_t>();
    }
    throw std::invalid_argument("expected a signed 64-bit Mesh integer");
}

/// Decode a Mesh scalar, preserving the signed, unsigned, or floating representation.
AtomicValue read_scalar(const json& value) {
    switch (value.type()) {
    case json::value_t::boolean:
        return value.get<bool>();
    case json::value_t::number_integer:
        return value.get<std::int64_t>();
    case json::value_t::number_unsigned:
        return value.get<std::uint64_t>();
    case json::value_t::number_float:
        return value.get<double>();
    case json::value_t::string:
        return value.get<std::string>();
    default:
        throw std::invalid_argument("expected a Mesh scalar");
    }
}

/// Decode a scalar or one-level collection of scalars.
BaseValue read_value(const json& value) {
    if (value.is_array()) {
        AtomicArray array;
        array.reserve(value.size());
        for (const auto& entry : value) {
            array.push_back(read_scalar(entry));
        }
        return array;
    }
    if (value.is_object()) {
        AtomicObject object;
        for (const auto& [key, entry] : value.items()) {
            object.emplace(key, read_scalar(entry));
        }
        return object;
    }
    return std::visit([](auto scalar) -> BaseValue { return scalar; }, read_scalar(value));
}

/// Encode a Mesh value without silently converting non-finite numbers to null.
json write_value(const BaseValue& value) {
    if (!is_valid_value(value)) {
        throw std::invalid_argument("a Mesh value contains a non-finite number");
    }
    const auto write_scalar = [](const auto& scalar) -> json { return json(scalar); };
    return std::visit([&](const auto& item) -> json {
        using Type = std::decay_t<decltype(item)>;
        if constexpr (std::is_same_v<Type, AtomicArray>) {
            auto array = json::array();
            for (const auto& entry : item) {
                array.push_back(std::visit(write_scalar, entry));
            }
            return array;
        } else if constexpr (std::is_same_v<Type, AtomicObject>) {
            auto object = json::object();
            for (const auto& [key, entry] : item) {
                object[key] = std::visit(write_scalar, entry);
            }
            return object;
        } else {
            return write_scalar(item);
        }
    }, value);
}

/// Decode an ordered list of invocation values.
std::vector<BaseValue> read_values(const json& value) {
    if (!value.is_array()) {
        throw std::invalid_argument("expected a Mesh value array");
    }
    std::vector<BaseValue> result;
    result.reserve(value.size());
    for (const auto& item : value) {
        result.push_back(read_value(item));
    }
    return result;
}

/// Encode an ordered list of invocation values.
json write_values(const std::vector<BaseValue>& values) {
    auto result = json::array();
    for (const auto& item : values) {
        result.push_back(write_value(item));
    }
    return result;
}

} // namespace

/// Decode both required error fields.
void from_json(const json& value, MeshError& error) {
    error = {read_integer(value.at("code")), value.at("message").get<std::string>()};
}

/// Encode the wire error object.
void to_json(json& value, const MeshError& error) {
    value = {{"code", error.code}, {"message", error.message}};
}

namespace {

/// Check the payload object and decode optional error details.
std::optional<MeshError> read_error(const json& payload) {
    if (!payload.is_object()) {
        throw std::invalid_argument("expected a Mesh payload object");
    }
    const auto error = payload.find("error");
    if (error == payload.end() || error->is_null()) {
        return std::nullopt;
    }
    return error->get<MeshError>();
}

/// Encode an absent error as JSON null.
json write_error(const std::optional<MeshError>& error) {
    return error ? json(*error) : json(nullptr);
}

} // namespace

/// Decode the required greeting fields.
void from_json(const json& value, Greeting& greeting) {
    greeting = {
        value.at("node_id").get<NodeId>(), value.at("name").get<std::string>(),
        read_integer(value.at("version")),
    };
}

/// Encode the wire greeting object.
void to_json(json& value, const Greeting& greeting) {
    value = {{"node_id", greeting.node_id}, {"name", greeting.name}, {"version", greeting.version}};
}

/// Decode the required route fields.
void from_json(const json& value, Friend& route) {
    route = {
        value.at("id").get<NodeId>(), value.at("name").get<std::string>(),
        read_integer(value.at("version")), read_integer(value.at("distance")),
        value.at("via").get<NodeId>(), value.at("detours").get<std::vector<NodeId>>(),
    };
}

/// Encode the wire route object.
void to_json(json& value, const Friend& route) {
    value = {{"id", route.id}, {"name", route.name}, {"version", route.version},
             {"distance", route.distance}, {"via", route.via}, {"detours", route.detours}};
}

/// Decode the required parameter fields.
void from_json(const json& value, Parameter& parameter) {
    parameter = {
        value.at("name").get<std::string>(), read_value(value.at("type")),
        value.at("description").get<std::string>(),
    };
}

/// Encode the wire parameter object.
void to_json(json& value, const Parameter& parameter) {
    value = {{"name", parameter.name}, {"type", write_value(parameter.type)},
             {"description", parameter.description}};
}

/// Decode the required capability fields.
void from_json(const json& value, Capability& capability) {
    capability = {
        value.at("node").get<NodeId>(), value.at("id").get<CmdId>(),
        value.at("name").get<std::string>(), value.at("description").get<std::string>(),
        value.at("input").get<std::vector<Parameter>>(), value.at("output").get<std::vector<Parameter>>(),
    };
}

/// Encode the wire capability object.
void to_json(json& value, const Capability& capability) {
    value = {{"node", capability.node}, {"id", capability.id}, {"name", capability.name},
             {"description", capability.description}, {"input", capability.input}, {"output", capability.output}};
}

/// Decode the required message metadata.
void from_json(const json& value, MessageMeta& meta) {
    meta = {
        read_integer(value.at("version")), value.at("node_from").get<NodeId>(),
        value.at("node_to").get<NodeId>(), value.at("hops").get<std::vector<NodeId>>(),
    };
}

/// Encode the wire metadata object.
void to_json(json& value, const MessageMeta& meta) {
    value = {{"version", meta.version}, {"node_from", meta.node_from},
             {"node_to", meta.node_to}, {"hops", meta.hops}};
}

/// Decode the payload in either greeting direction.
template <bool IsAcknowledgement>
void from_json(const json& value, GreetingPayload<IsAcknowledgement>& payload) {
    payload = {value.at("greeting").get<Greeting>(), read_error(value)};
}

/// Encode the shared greeting payload shape.
template <bool IsAcknowledgement>
void to_json(json& value, const GreetingPayload<IsAcknowledgement>& payload) {
    value = {{"greeting", payload.greeting}, {"error", write_error(payload.error)}};
}

/// Decode a route discovery request.
void from_json(const json& value, FriendsPayload& payload) {
    payload = {read_integer(value.at("max_distance")), read_error(value)};
}

/// Encode a route discovery request.
void to_json(json& value, const FriendsPayload& payload) {
    value = {{"max_distance", payload.max_distance}, {"error", write_error(payload.error)}};
}

/// Decode advertised routes.
void from_json(const json& value, FriendsAckPayload& payload) {
    payload = {value.at("friends").get<std::vector<Friend>>(), read_error(value)};
}

/// Encode advertised routes.
void to_json(json& value, const FriendsAckPayload& payload) {
    value = {{"friends", payload.friends}, {"error", write_error(payload.error)}};
}

/// Decode a capability discovery request.
void from_json(const json& value, CanPayload& payload) {
    payload = {read_error(value)};
}

/// Encode a capability discovery request.
void to_json(json& value, const CanPayload& payload) {
    value = {{"error", write_error(payload.error)}};
}

/// Decode advertised capabilities.
void from_json(const json& value, CanAckPayload& payload) {
    payload = {value.at("can").get<std::vector<Capability>>(), read_error(value)};
}

/// Encode advertised capabilities.
void to_json(json& value, const CanAckPayload& payload) {
    value = {{"can", payload.can}, {"error", write_error(payload.error)}};
}

/// Decode a capability invocation request.
void from_json(const json& value, DoPayload& payload) {
    payload = {value.at("id").get<CmdId>(), read_values(value.at("input")), read_error(value)};
}

/// Encode a capability invocation request.
void to_json(json& value, const DoPayload& payload) {
    value = {{"id", payload.id}, {"input", write_values(payload.input)}, {"error", write_error(payload.error)}};
}

/// Decode capability invocation outputs.
void from_json(const json& value, DoAckPayload& payload) {
    payload = {read_values(value.at("outputs")), read_error(value)};
}

/// Encode capability invocation outputs.
void to_json(json& value, const DoAckPayload& payload) {
    value = {{"outputs", write_values(payload.outputs)}, {"error", write_error(payload.error)}};
}

namespace {

/// Construct the payload selected by a wire discriminator.
template <typename Type>
Payload read_payload(const json& payload) {
    return payload.get<Type>();
}

/// Pair a wire discriminator with its payload decoder.
template <typename Type>
constexpr auto decoder = std::pair{Type::kind, &read_payload<Type>};

constexpr std::array payload_decoders{
    decoder<HelloPayload>, decoder<HelloAckPayload>, decoder<FriendsPayload>, decoder<FriendsAckPayload>,
    decoder<CanPayload>, decoder<CanAckPayload>, decoder<DoPayload>, decoder<DoAckPayload>,
};

} // namespace

Message parse_message(std::string_view data) {
    // The JSON lexer treats a raw NUL as end-of-input even for an iterator range.
    if (data.find('\0') != std::string_view::npos) {
        throw std::invalid_argument("unexpected NUL byte in Mesh JSON");
    }
    try {
        const auto wire = json::parse(data.begin(), data.end());
        const auto kind = wire.at("msg").get<std::string>();
        for (const auto& [name, decode] : payload_decoders) {
            if (name == kind) {
                return {wire.at("meta").get<MessageMeta>(), decode(wire.at("payload"))};
            }
        }
        throw std::invalid_argument("unknown Mesh message type: " + kind);
    } catch (const json::exception& error) {
        throw std::invalid_argument(error.what());
    }
}

std::string encode_message(const Message& message) {
    try {
        return std::visit([&](const auto& payload) {
            return json{{"msg", payload.kind}, {"meta", message.meta}, {"payload", payload}}.dump();
        }, message.payload);
    } catch (const json::exception& error) {
        throw std::invalid_argument(error.what());
    }
}

} // namespace lange_mesh
