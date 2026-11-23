#include <lange_mesh/tool_group.hpp>

#include <algorithm>
#include <utility>

namespace lange_mesh {

ToolGroup::ToolGroup(NodeId owner) : owner_(std::move(owner)) {}

void ToolGroup::add_to_mesh(Capability capability, ToolHandler handler) {
    register_tool({std::move(capability), std::make_shared<ToolHandler>(std::move(handler))});
}

void ToolGroup::add_tool_group(const ToolGroup& source) {
    if (this == &source) {
        return;
    }
    for (const auto& tool : source.tools_) {
        register_tool(tool);
    }
}

void ToolGroup::register_tool(RegisteredTool tool) {
    tool.capability.node = owner_;
    const auto found = std::find_if(tools_.begin(), tools_.end(), [&](const RegisteredTool& existing) {
        return existing.capability.id == tool.capability.id;
    });
    if (found == tools_.end()) {
        tools_.push_back(std::move(tool));
    } else {
        *found = std::move(tool);
    }
}

std::vector<Capability> ToolGroup::capabilities() const {
    std::vector<Capability> result;
    result.reserve(tools_.size());
    for (const auto& tool : tools_) {
        result.push_back(tool.capability);
    }
    return result;
}

DoAckPayload ToolGroup::invoke(const CmdId& id, const std::vector<BaseValue>& input) const {
    const auto found = std::find_if(tools_.begin(), tools_.end(), [&](const RegisteredTool& tool) {
        return tool.capability.id == id;
    });
    if (found == tools_.end()) {
        return {{}, MeshError{404, "Unknown capability"}};
    }

    // Keep the handler alive if it changes its own registration during the call.
    const auto handler = found->handler;
    ToolResult output;
    try {
        output = (*handler)(input);
    } catch (...) {
        return {{}, MeshError{500, "Capability invocation failed"}};
    }
    if (!output) {
        return {};
    }
    if (!is_valid_value(*output)) {
        return {{}, MeshError{500, "Capability invocation failed"}};
    }
    DoAckPayload result;
    result.outputs.push_back(std::move(*output));
    return result;
}

} // namespace lange_mesh
