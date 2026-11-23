#pragma once

#include <lange_mesh/messages.hpp>

#include <functional>
#include <memory>

namespace lange_mesh {

/// A capability's output, with nullopt representing empty outputs.
using ToolResult = std::optional<BaseValue>;

/// A local capability. Exceptions become generic Mesh invocation failures.
using ToolHandler = std::function<ToolResult(const std::vector<BaseValue>&)>;

/// An ordered set of local capabilities advertised under a common owner.
class ToolGroup {
public:
    /// Create an empty capability group for the given owner.
    explicit ToolGroup(NodeId owner);

    /// Register or replace a tool using explicit discovery metadata.
    void add_to_mesh(Capability capability, ToolHandler handler);

    /// Copy another group's tool registrations under this group's owner.
    void add_tool_group(const ToolGroup& source);

    /// Return discovery descriptions in registration order.
    std::vector<Capability> capabilities() const;

    /// Invoke a registered tool and return its output or protocol error.
    DoAckPayload invoke(const CmdId& id, const std::vector<BaseValue>& input) const;

private:
    /// The discovery description and callable for a capability.
    struct RegisteredTool {
        Capability capability;
        std::shared_ptr<const ToolHandler> handler;
    };

    /// Store a tool under this group's owner while preserving registration order.
    void register_tool(RegisteredTool tool);

    NodeId owner_;
    std::vector<RegisteredTool> tools_;
};

} // namespace lange_mesh
