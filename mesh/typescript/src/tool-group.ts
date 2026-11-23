import type { DoAckPayload } from "./messages.js";
import type { BaseTypes, Can, CmdId, NodeId } from "./types.js";
import { isBaseValue } from "./validation.js";

/** A capability's declared metadata before registration assigns its owner. */
export type ToolDescription = Omit<Can, "node">;

/** An async local capability. A missing return value produces empty outputs. */
export type ToolHandler = (inputs: readonly BaseTypes[]) => Promise<BaseTypes | void>;

interface RegisteredTool {
  capability: Can;
  handler: ToolHandler;
}

/** A collection of local capabilities advertised under a common node ID. */
export class MeshToolGroup {
  private readonly registered = new Map<CmdId, RegisteredTool>();

  /** Create an empty capability group owned by the given node. */
  constructor(private readonly nodeId: NodeId) {}

  /** Register or replace a tool using explicit discovery metadata. */
  addToMesh(description: ToolDescription, handler: ToolHandler): void {
    const capability = structuredClone({ ...description, node: this.nodeId });
    this.registered.set(capability.id, { capability, handler });
  }

  /** Copy a group's current tools under this group's owner ID, replacing matching IDs. */
  addToolGroup(group: MeshToolGroup): void {
    for (const { capability, handler } of group.registered.values()) {
      this.addToMesh(capability, handler);
    }
  }

  /** Return the capability descriptions in registration order. */
  capabilities(): Can[] {
    return Array.from(this.registered.values(), ({ capability }): Can => structuredClone(capability));
  }

  /** Invoke a registered tool and translate its result or failure to a Mesh payload. */
  async invoke(id: CmdId, inputs: readonly BaseTypes[]): Promise<DoAckPayload> {
    const tool = this.registered.get(id);
    if (!tool) {
      return { outputs: [], error: { code: 404, message: "Unknown capability" } };
    }

    try {
      const result = await tool.handler(inputs);
      if (result === undefined) {
        return { outputs: [], error: null };
      }
      if (isBaseValue(result)) {
        return { outputs: [result], error: null };
      }
    } catch {
      // Keep exception details local to the tool.
    }
    return { outputs: [], error: { code: 500, message: "Capability invocation failed" } };
  }
}
