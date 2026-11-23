# Mesh messages

Mesh nodes use a common envelope for requests and acknowledgements. The `msg`
field identifies the payload shape. A leading `-` identifies an acknowledgement.

| Field | Type | Required | Content |
| --- | --- | --- | --- |
| `meta` | object | Yes | Sender, destination, version, and hop information. |
| `meta.version` | integer | Yes | Version ID supplied by the sending node. |
| `meta.node_from` | string | Yes | Sender node ID. |
| `meta.node_to` | string | Yes | Destination node ID. |
| `meta.hops` | array of strings | Yes | Ordered node IDs along the message path. The Python router starts replies with its own ID. |
| `msg` | string | Yes | One of `hello`, `-hello`, `friends`, `-friends`, `can`, `-can`, `do`, or `-do`. |
| `payload` | object | Yes | Fields defined by the message type. |
| `payload.error` | object or `null` | No | Error details when present. Defaults to `null`. |
| `payload.error.code` | integer | If `error` is an object | Error code. |
| `payload.error.message` | string | If `error` is an object | Error description. |

Each concrete Python message model fills in its own `msg` value by default.

| Request | Acknowledgement | Purpose |
| --- | --- | --- |
| [`hello`](hello.md) | `-hello` | Exchange node identity and version. |
| [`friends`](friends.md) | `-friends` | Discover reachable nodes and routes. |
| [`can`](can.md) | `-can` | Discover capabilities and their parameters. |
| [`do`](do.md) | `-do` | Invoke a capability and return its result. |

`NodeId` and `CmdId` are strings. `VersionId` is an integer. A base value is an
integer, floating-point number, string, boolean, array of those scalar types,
or object with string keys and scalar values.
