# Lange Mesh for TypeScript

`lange-mesh` implements the [Mesh wire messages](../../reference_documentation/messages/README.md), local routing, and async capabilities. Use it as an ES module on Node.js 22 or later.

```sh
npm ci
npm test
npm pack
```

Install the resulting archive in your application with
`npm install /path/to/lange-mesh-0.1.0.tgz`.

```ts
import { MeshRouter, parseMessage } from "lange-mesh";

const router = new MeshRouter({ node_id: "local", name: "Local", version: 1 });

router.tools.addToMesh(
  {
    id: "echo",
    name: "Echo",
    description: "Returns the supplied value.",
    input: [{ name: "value", type: "string", description: "The value to echo." }],
    output: [{ name: "value", type: "string", description: "The echoed value." }],
  },
  async ([value]) => value,
);

const outcome = await router.handleMessage(parseMessage(JSON.stringify({
  msg: "do",
  meta: { version: 1, node_from: "peer", node_to: "local", hops: ["peer"] },
  payload: { id: "echo", input: ["hello"] },
})));

if (outcome.kind === "reply") {
  console.log(JSON.stringify(outcome.message));
}
```

Pass incoming JSON through `parseMessage` and send replies through your application's transport. Acknowledgement outcomes expose their `msg` and typed `payload` to the local caller. Protocol integer fields use JavaScript's safe integer range. Each tool returns one Mesh value, or `undefined` for empty outputs.
