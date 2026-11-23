import type { MeshMsg, MeshMsgMeta } from "./messages.js";
import type { Can, CanParameter, Friend, MeshError } from "./types.js";
import { isBaseValue, isRecord } from "./validation.js";

/** Check whether a protocol integer is exactly representable as a JavaScript number. */
function isWireInteger(value: unknown): value is number {
  return typeof value === "number" && Number.isSafeInteger(value);
}

/** Check whether a path consists of node IDs. */
function isNodePath(value: unknown): value is string[] {
  return Array.isArray(value) && value.every((node: unknown): boolean => typeof node === "string");
}

/** Check the discovery description for a capability parameter. */
function isCanParameter(value: unknown): value is CanParameter {
  return isRecord(value) && typeof value.name === "string" && typeof value.description === "string"
    && isBaseValue(value.type);
}

/**
 * Decode and validate a JSON Mesh message, defaulting an omitted payload error to null.
 *
 * @throws {SyntaxError} If the input is invalid JSON.
 * @throws {TypeError} If its envelope or payload does not match the Mesh wire schema.
 */
export function parseMessage(json: string): MeshMsg {
  const wire: unknown = JSON.parse(json);
  if (!isRecord(wire) || !isRecord(wire.meta) || !isRecord(wire.payload)) {
    throw new TypeError("Invalid Mesh message envelope");
  }
  const { msg, payload } = wire;
  const { version, node_from, node_to, hops } = wire.meta;
  if (!isWireInteger(version) || typeof node_from !== "string"
      || typeof node_to !== "string" || !isNodePath(hops)) {
    throw new TypeError("Invalid Mesh message metadata");
  }
  const meta: MeshMsgMeta = { version, node_from, node_to, hops };

  let error: MeshError | null = null;
  if (payload.error !== undefined && payload.error !== null) {
    if (!isRecord(payload.error) || !isWireInteger(payload.error.code)
        || typeof payload.error.message !== "string") {
      throw new TypeError("Invalid Mesh payload error");
    }
    error = { code: payload.error.code, message: payload.error.message };
  }

  switch (msg) {
    case "hello":
    case "-hello": {
      const { greeting } = payload;
      if (!isRecord(greeting) || typeof greeting.node_id !== "string"
          || typeof greeting.name !== "string" || !isWireInteger(greeting.version)) {
        break;
      }
      const { node_id, name, version } = greeting;
      return { msg, meta, payload: { greeting: { node_id, name, version }, error } };
    }
    case "friends": {
      const { max_distance } = payload;
      if (!isWireInteger(max_distance)) {
        break;
      }
      return { msg, meta, payload: { max_distance, error } };
    }
    case "-friends": {
      const { friends } = payload;
      if (!Array.isArray(friends) || !friends.every((friend: unknown): friend is Friend =>
        isRecord(friend) && typeof friend.id === "string" && typeof friend.name === "string"
          && isWireInteger(friend.version) && isWireInteger(friend.distance)
          && typeof friend.via === "string" && isNodePath(friend.detours)
      )) {
        break;
      }
      return { msg, meta, payload: { friends, error } };
    }
    case "can":
      return { msg, meta, payload: { error } };
    case "-can": {
      const { can } = payload;
      if (!Array.isArray(can) || !can.every((capability: unknown): capability is Can =>
        isRecord(capability) && typeof capability.node === "string" && typeof capability.id === "string"
          && typeof capability.name === "string" && typeof capability.description === "string"
          && Array.isArray(capability.input) && capability.input.every(isCanParameter)
          && Array.isArray(capability.output) && capability.output.every(isCanParameter)
      )) {
        break;
      }
      return { msg, meta, payload: { can, error } };
    }
    case "do": {
      const { id, input } = payload;
      if (typeof id !== "string" || !Array.isArray(input) || !input.every(isBaseValue)) {
        break;
      }
      return { msg, meta, payload: { id, input, error } };
    }
    case "-do": {
      const { outputs } = payload;
      if (!Array.isArray(outputs) || !outputs.every(isBaseValue)) {
        break;
      }
      return { msg, meta, payload: { outputs, error } };
    }
    default:
      throw new TypeError("Unknown Mesh message type");
  }
  throw new TypeError(`Invalid Mesh payload for ${msg}`);
}
