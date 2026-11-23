import type { BaseTypes, Can, CmdId, Friend, Greeting, MeshError, NodeId, VersionId } from "./types.js";

/** The sender, destination, version, and path shared by all messages. */
export interface MeshMsgMeta {
  version: VersionId;
  node_from: NodeId;
  node_to: NodeId;
  hops: NodeId[];
}

/** Optional error details shared by each payload. */
export interface MeshPayload {
  error?: MeshError | null;
}

/** The metadata and typed payload carried by a wire message. */
export interface MeshMsgEnvelope<Kind extends string, Payload extends MeshPayload> {
  msg: Kind;
  meta: MeshMsgMeta;
  payload: Payload;
}

/** An identity exchanged in either greeting direction. */
export interface HelloPayload extends MeshPayload {
  greeting: Greeting;
}

/** The maximum requested distance for an advertised route. */
export interface FriendsPayload extends MeshPayload {
  max_distance: number;
}

/** The routes advertised by a responding node. */
export interface FriendsAckPayload extends MeshPayload {
  friends: Friend[];
}

/** The capability descriptions advertised by a responding node. */
export interface CanAckPayload extends MeshPayload {
  can: Can[];
}

/** A command ID and its ordered arguments. */
export interface DoPayload extends MeshPayload {
  id: CmdId;
  input: BaseTypes[];
}

/** The outputs or error of a capability invocation. */
export interface DoAckPayload extends MeshPayload {
  outputs: BaseTypes[];
}

/** All acknowledgement messages, discriminated by their wire names. */
export type MeshAck =
  | MeshMsgEnvelope<"-hello", HelloPayload>
  | MeshMsgEnvelope<"-friends", FriendsAckPayload>
  | MeshMsgEnvelope<"-can", CanAckPayload>
  | MeshMsgEnvelope<"-do", DoAckPayload>;

/** All request and acknowledgement messages accepted by a node. */
export type MeshMsg =
  | MeshMsgEnvelope<"hello", HelloPayload>
  | MeshMsgEnvelope<"friends", FriendsPayload>
  | MeshMsgEnvelope<"can", MeshPayload>
  | MeshMsgEnvelope<"do", DoPayload>
  | MeshAck;
