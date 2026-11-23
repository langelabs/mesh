/** A Mesh node identifier. */
export type NodeId = string;

/** The identifier of an advertised capability. */
export type CmdId = string;

/** The integer version advertised by a node. */
export type VersionId = number;

/** A scalar in a Mesh payload. Numbers must be finite. */
export type AtomicTypes = number | string | boolean;

/** A scalar or a one-level collection of scalars. */
export type BaseTypes = AtomicTypes | AtomicTypes[] | Record<string, AtomicTypes>;

/** An error carried in a Mesh payload. */
export interface MeshError {
  code: number;
  message: string;
}

/** The identity and version advertised by a node. */
export interface Greeting {
  node_id: NodeId;
  name: string;
  version: VersionId;
}

/** A known peer and the next hops that can reach it. */
export interface Friend {
  id: NodeId;
  name: string;
  version: VersionId;
  distance: number;
  via: NodeId;
  detours: NodeId[];
}

/** The description of an individual capability parameter. */
export interface CanParameter {
  name: string;
  type: BaseTypes;
  description: string;
}

/** The discovery metadata for a capability advertised by a node. */
export interface Can {
  node: NodeId;
  id: CmdId;
  name: string;
  description: string;
  input: CanParameter[];
  output: CanParameter[];
}
