#pragma once

#include <cstdint>
#include <map>
#include <string>
#include <variant>
#include <vector>

namespace lange_mesh {

/// A mesh node identifier.
using NodeId = std::string;
/// An identifier for an advertised capability.
using CmdId = std::string;
/// A node's advertised protocol version.
using VersionId = std::int64_t;

/// A scalar on the Mesh wire. Floating-point values must be finite.
using AtomicValue = std::variant<bool, std::int64_t, std::uint64_t, double, std::string>;
using AtomicArray = std::vector<AtomicValue>;
using AtomicObject = std::map<std::string, AtomicValue>;

/// A scalar or a one-level collection of scalars.
using BaseValue = std::variant<bool, std::int64_t, std::uint64_t, double, std::string,
                               AtomicArray, AtomicObject>;

/// Check that every numeric component of a Mesh value is finite.
bool is_valid_value(const BaseValue& value);

/// An error carried in a message payload.
struct MeshError {
    std::int64_t code{};
    std::string message;
};

/// The identity and version advertised by a node.
struct Greeting {
    NodeId node_id;
    std::string name;
    VersionId version{};
};

/// A known peer and the available next hops to reach it.
struct Friend {
    NodeId id;
    std::string name;
    VersionId version{};
    std::int64_t distance{};
    NodeId via;
    std::vector<NodeId> detours;
};

/// A named input or output of a capability.
struct Parameter {
    std::string name;
    BaseValue type;
    std::string description;
};

/// The discovery description of a local capability.
struct Capability {
    NodeId node;
    CmdId id;
    std::string name;
    std::string description;
    std::vector<Parameter> input;
    std::vector<Parameter> output;
};

} // namespace lange_mesh
