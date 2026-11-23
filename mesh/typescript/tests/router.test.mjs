import assert from "node:assert/strict";
import test from "node:test";
import { MeshRouter, MeshToolGroup } from "lange-mesh";

const local = { node_id: "local", name: "Local", version: 7 };
const peer = { node_id: "peer", name: "Peer", version: 1 };
const echo = { id: "echo", name: "Echo", description: "Echo a value", input: [], output: [] };

/** Deliver a message to the local router. */
function dispatch(router, msg, payload, sender = peer.node_id) {
  return router.handleMessage({
    msg,
    meta: { version: peer.version, node_from: sender, node_to: local.node_id, hops: [sender] },
    payload,
  });
}

/** Check the reply envelope and return its payload. */
function replyPayload(outcome, msg, recipient = peer.node_id) {
  assert.equal(outcome.kind, "reply");
  assert.equal(outcome.message.msg, msg);
  assert.deepEqual(outcome.message.meta, {
    version: local.version, node_from: local.node_id, node_to: recipient, hops: [local.node_id],
  });
  return outcome.message.payload;
}

/** Describe a peer route with optional alternate next hops. */
function route(id, distance, via, detours = []) {
  return { id, name: id, version: 1, distance, via, detours };
}

test("answers greetings with the local identity", async () => {
  const router = new MeshRouter(local);
  const reply = await dispatch(router, "hello", { greeting: peer });
  assert.deepEqual(replyPayload(reply, "-hello"), { greeting: local, error: null });
  assert.equal(router.friend("peer").distance, 1);
  assert.equal(router.friend("peer").via, "peer");
});

test("learns direct routes from greeting acknowledgements", async () => {
  const router = new MeshRouter(local);
  const payload = { greeting: peer, error: null };
  assert.deepEqual(await dispatch(router, "-hello", payload), {
    kind: "acknowledgement", msg: "-hello", payload,
  });
  assert.equal(router.friend("peer").distance, 1);
});

test("keeps the shortest route with unique detours and preserves the first route on ties", async () => {
  const router = new MeshRouter(local);
  await dispatch(router, "-friends", {
    friends: [route("a", 3, "peer", ["backup"]), route("b", 2, "peer"), route("local", 1, "peer")],
  });
  const payload = {
    friends: [route("a", 2, "other", ["backup", "other"]), route("b", 2, "other")],
  };
  assert.deepEqual(await dispatch(router, "-friends", payload, "other"), {
    kind: "acknowledgement", msg: "-friends", payload,
  });
  assert.deepEqual(router.friend("a"), route("a", 2, "other", ["backup", "peer"]));
  assert.deepEqual(router.friend("b"), route("b", 2, "peer", ["other"]));
  assert.equal(router.friend("local"), undefined);
});

test("advertises routes within the limit that do not lead back through the requester", async () => {
  const router = new MeshRouter(local);
  const near = route("near", 2, "other", ["backup"]);
  await dispatch(router, "-friends", {
    friends: [near, route("far", 3, "other"), route("back", 2, "peer")],
  }, "other");
  const reply = await dispatch(router, "friends", { max_distance: 3 });
  assert.deepEqual(replyPayload(reply, "-friends"), {
    friends: [route("near", 3, "local")], error: null,
  });
  reply.message.payload.friends[0].detours.push("changed");
  const friend = router.friend("near");
  friend.detours.push("changed");
  assert.deepEqual(router.friend("near"), near);
});

test("advertises copied tools under the router identity", async () => {
  const router = new MeshRouter(local);
  const leaf = new MeshToolGroup("leaf");
  const parent = new MeshToolGroup("parent");
  leaf.addToMesh(echo, async ([value]) => value);
  parent.addToolGroup(leaf);
  router.tools.addToolGroup(parent);
  leaf.addToMesh(echo, async () => "replacement");
  const reply = await dispatch(router, "can", {});
  const payload = replyPayload(reply, "-can");
  assert.deepEqual(payload, { can: [{ ...echo, node: "local" }], error: null });
  assert.deepEqual(await dispatch(router, "-can", payload), {
    kind: "acknowledgement", msg: "-can", payload,
  });
  const invoked = await dispatch(router, "do", { id: "echo", input: ["original"] });
  assert.deepEqual(replyPayload(invoked, "-do"), { outputs: ["original"], error: null });
});

test("returns an array result in one output slot", async () => {
  const router = new MeshRouter(local);
  router.tools.addToMesh(echo, async ([, value]) => value);
  const reply = await dispatch(router, "do", { id: "echo", input: ["first", [1, 2]] });
  assert.deepEqual(replyPayload(reply, "-do"), { outputs: [[1, 2]], error: null });
});

test("represents a tool without a return value as empty outputs", async () => {
  const router = new MeshRouter(local);
  router.tools.addToMesh(echo, async () => {});
  const reply = await dispatch(router, "do", { id: "echo", input: [] });
  assert.deepEqual(replyPayload(reply, "-do"), { outputs: [], error: null });
});

test("reports unknown command IDs with a 404", async () => {
  const router = new MeshRouter(local);
  const reply = await dispatch(router, "do", { id: "__proto__", input: [] });
  assert.deepEqual(replyPayload(reply, "-do"), {
    outputs: [], error: { code: 404, message: "Unknown capability" },
  });
});

test("reports tool failures without exposing exception details", async () => {
  const router = new MeshRouter(local);
  router.tools.addToMesh(echo, async () => { throw new Error("private details"); });
  const reply = await dispatch(router, "do", { id: "echo", input: [] });
  const payload = replyPayload(reply, "-do");
  assert.deepEqual(payload, {
    outputs: [], error: { code: 500, message: "Capability invocation failed" },
  });
  assert.deepEqual(await dispatch(router, "-do", payload), {
    kind: "acknowledgement", msg: "-do", payload,
  });
});

test("rejects results that cannot be represented as Mesh base values", async () => {
  const router = new MeshRouter(local);
  router.tools.addToMesh(echo, async () => ({ invalid: Infinity }));
  const reply = await dispatch(router, "do", { id: "echo", input: [] });
  assert.equal(replyPayload(reply, "-do").error.code, 500);
});
