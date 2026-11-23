package mesh

import (
	"slices"
	"sync"
)

// ToolHandler invokes a capability. A nil value with no error means empty outputs.
// Handlers may be called concurrently by concurrent requests.
type ToolHandler func([]BaseValue) (*BaseValue, error)

// registeredTool pairs an advertised capability with its implementation.
type registeredTool struct {
	capability Capability
	handler    ToolHandler
}

// ToolGroup stores local capabilities under a common owner ID.
// Its methods are safe for concurrent use. Do not copy a ToolGroup after first use.
type ToolGroup struct {
	owner NodeID
	mu    sync.RWMutex
	tools []registeredTool
	index map[CmdID]int
}

// NewToolGroup creates an empty capability group owned by the given node.
func NewToolGroup(owner NodeID) *ToolGroup {
	return &ToolGroup{owner: owner, index: make(map[CmdID]int)}
}

// AddToMesh registers or replaces a capability using the group's owner ID.
func (g *ToolGroup) AddToMesh(capability Capability, handler ToolHandler) {
	g.mu.Lock()
	defer g.mu.Unlock()
	g.register(registeredTool{copyCapability(capability), handler})
}

// AddToolGroup snapshots the source group's tools and registers them under this owner.
func (g *ToolGroup) AddToolGroup(source *ToolGroup) {
	if g == source {
		return
	}
	source.mu.RLock()
	tools := slices.Clone(source.tools)
	source.mu.RUnlock()

	g.mu.Lock()
	defer g.mu.Unlock()
	for _, tool := range tools {
		g.register(tool)
	}
}

// register stores a tool while the group's write lock is held.
func (g *ToolGroup) register(tool registeredTool) {
	tool.capability.Node = g.owner
	id := tool.capability.ID
	if index, exists := g.index[id]; exists {
		g.tools[index] = tool
		return
	}
	g.index[id] = len(g.tools)
	g.tools = append(g.tools, tool)
}

// Capabilities returns discovery descriptions in registration order.
func (g *ToolGroup) Capabilities() []Capability {
	g.mu.RLock()
	defer g.mu.RUnlock()
	capabilities := make([]Capability, 0, len(g.tools))
	for _, tool := range g.tools {
		capabilities = append(capabilities, copyCapability(tool.capability))
	}
	return capabilities
}

// copyCapability snapshots the mutable slices of capability metadata.
func copyCapability(capability Capability) Capability {
	capability.Input = slices.Clone(capability.Input)
	capability.Output = slices.Clone(capability.Output)
	return capability
}

// Invoke calls a capability and turns its result or failure into a wire payload.
func (g *ToolGroup) Invoke(id CmdID, input []BaseValue) (result DoAckPayload) {
	g.mu.RLock()
	index, exists := g.index[id]
	var handler ToolHandler
	if exists {
		handler = g.tools[index].handler
	}
	g.mu.RUnlock()
	if !exists {
		result.Error = &MeshError{Code: 404, Message: "Unknown capability"}
		return result
	}

	failure := MeshError{Code: 500, Message: "Capability invocation failed"}
	defer func() {
		if recover() != nil {
			result.Error = &failure
		}
	}()
	value, err := handler(input)
	switch {
	case err != nil || (value != nil && value.value == nil):
		result.Error = &failure
	case value != nil:
		result.Outputs = List[BaseValue]{*value}
	}
	return result
}
