import assert from "node:assert/strict";
import test from "node:test";
import { parseMessage } from "lange-mesh";

const meta = { version: 1, node_from: "peer", node_to: "local", hops: ["peer"] };
const greeting = { node_id: "peer", name: "Peer", version: 1 };
const friend = {
  id: "friend", name: "Friend", version: 1, distance: 2, via: "peer", detours: ["other"],
};
const parameter = { name: "text", type: "str", description: "Input" };
const capability = {
  node: "peer", id: "echo", name: "Echo", description: "Echoes a value",
  input: [parameter], output: [],
};

test("parses all eight Mesh wire messages", () => {
  for (const [msg, payload] of [
    ["hello", { greeting }],
    ["-hello", { greeting }],
    ["friends", { max_distance: 3 }],
    ["-friends", { friends: [friend] }],
    ["can", {}],
    ["-can", { can: [capability] }],
    ["do", { id: "echo", input: [1, 1.25, "text", true, ["a", 2], { ready: false }] }],
    ["-do", { outputs: [["a", 2]], error: null }],
    ["-do", { outputs: [], error: { code: 404, message: "Unknown capability" } }],
  ]) {
    const wire = { msg, meta, payload };
    assert.deepEqual(parseMessage(JSON.stringify(wire)), {
      ...wire, payload: { error: null, ...payload },
    }, msg);
  }
});

test("rejects malformed Mesh wire messages", () => {
  for (const wire of [
    { msg: "ping", meta, payload: {} },
    { msg: "can", payload: {} },
    { msg: "can", meta: { ...meta, version: 1.5 }, payload: {} },
    { msg: "can", meta: { ...meta, hops: [2] }, payload: {} },
    { msg: "hello", meta, payload: {} },
    { msg: "friends", meta, payload: { max_distance: "3" } },
    { msg: "-friends", meta, payload: { friends: [{ ...friend, detours: false }] } },
    { msg: "-can", meta, payload: { can: null } },
    { msg: "-can", meta, payload: { can: [{ ...capability, input: [null] }] } },
    { msg: "do", meta, payload: { id: "echo", input: [[["nested"]]] } },
    { msg: "do", meta, payload: { id: "echo", input: [{ nested: [1] }] } },
    { msg: "do", meta, payload: { id: "echo", input: [null] } },
    { msg: "can", meta, payload: { error: { code: 500 } } },
  ]) {
    assert.throws(() => parseMessage(JSON.stringify(wire)), TypeError, JSON.stringify(wire));
  }
  assert.throws(() => parseMessage("{"), SyntaxError);
});
