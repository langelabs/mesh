import type { MeshAck, MeshMsg, MeshMsgMeta } from "./messages.js";
import { MeshToolGroup } from "./tool-group.js";
import type { Friend, Greeting, NodeId } from "./types.js";

/** An acknowledgement delivered to a local caller, with its payload type preserved. */
export type AckOutcome = {
  [Kind in MeshAck["msg"]]: {
    kind: "acknowledgement";
    msg: Kind;
    payload: Extract<MeshAck, { msg: Kind }>["payload"];
  };
}[MeshAck["msg"]];

/** A wire reply to send back or an acknowledgement for the local caller. */
export type RouteOutcome =
  | { kind: "reply"; message: MeshAck }
  | AckOutcome;

/** A node's local identity, registered capabilities, and known peer routes. */
export class MeshRouter {
  readonly tools: MeshToolGroup;
  private readonly identity: Greeting;
  private readonly friends = new Map<NodeId, Friend>();

  /** Create a local router with the supplied node identity. */
  constructor(identity: Greeting) {
    this.identity = { ...identity };
    this.tools = new MeshToolGroup(identity.node_id);
  }

  /** Return a snapshot of the known route to the given node. */
  friend(nodeId: NodeId): Friend | undefined {
    const friend = this.friends.get(nodeId);
    return friend && { ...friend, detours: [...friend.detours] };
  }

  /** Dispatch a message delivered to this node and return its local outcome. */
  async handleMessage(message: MeshMsg): Promise<RouteOutcome> {
    const { msg, meta, payload } = message;
    switch (msg) {
      case "hello":
      case "-hello": {
        const { node_id, name, version } = payload.greeting;
        this.mergeFriends([{ id: node_id, name, version, distance: 1, via: node_id, detours: [] }]);
        if (msg === "-hello") {
          return { kind: "acknowledgement", msg, payload };
        }
        return {
          kind: "reply",
          message: {
            msg: "-hello",
            meta: this.replyMeta(meta.node_from),
            payload: { greeting: { ...this.identity }, error: null },
          },
        };
      }
      case "friends": {
        const friends: Friend[] = [];
        for (const friend of this.friends.values()) {
          if (friend.distance < payload.max_distance && friend.via !== meta.node_from) {
            friends.push({
              ...friend, distance: friend.distance + 1, via: this.identity.node_id, detours: [],
            });
          }
        }
        return {
          kind: "reply",
          message: {
            msg: "-friends", meta: this.replyMeta(meta.node_from), payload: { friends, error: null },
          },
        };
      }
      case "-friends":
        this.mergeFriends(payload.friends);
        return { kind: "acknowledgement", msg, payload };
      case "can":
        return {
          kind: "reply",
          message: {
            msg: "-can",
            meta: this.replyMeta(meta.node_from),
            payload: { can: this.tools.capabilities(), error: null },
          },
        };
      case "-can":
        return { kind: "acknowledgement", msg, payload };
      case "do":
        return {
          kind: "reply",
          message: {
            msg: "-do",
            meta: this.replyMeta(meta.node_from),
            payload: await this.tools.invoke(payload.id, payload.input),
          },
        };
      case "-do":
        return { kind: "acknowledgement", msg, payload };
    }
  }

  /** Address a reply to the original sender with this node as its first hop. */
  private replyMeta(recipient: NodeId): MeshMsgMeta {
    const { node_id, version } = this.identity;
    return { version, node_from: node_id, node_to: recipient, hops: [node_id] };
  }

  /** Retain the shortest route and record alternate next hops in discovery order. */
  private mergeFriends(incoming: readonly Friend[]): void {
    for (const friend of incoming) {
      if (friend.id === this.identity.node_id) {
        continue;
      }

      const current = this.friends.get(friend.id);
      if (!current) {
        this.friends.set(friend.id, { ...friend, detours: [...friend.detours] });
        continue;
      }

      const [primary, alternate] = friend.distance < current.distance
        ? [friend, current]
        : [current, friend];
      const detours = new Set([...primary.detours, alternate.via, ...alternate.detours]);
      detours.delete(primary.via);
      this.friends.set(friend.id, { ...primary, detours: [...detours] });
    }
  }
}
