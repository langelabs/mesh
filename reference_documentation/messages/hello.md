# Hello messages

Two directly connected nodes exchange identity and version information with
`hello` and `-hello`. A recipient can use the greeting to learn a direct route
to the sender. Both messages use the [common envelope](README.md).

## Request (`hello`)

A direct transport discovery request may set `meta.node_to` to `""` when the
destination node ID is unknown. The acknowledgement sets `meta.node_from` to
the recipient's node ID and `meta.node_to` to the request sender's node ID.

| Payload field | Type | Content |
| --- | --- | --- |
| `greeting` | object | Identity of the node initiating the exchange. |
| `greeting.node_id` | string | Node ID of the peer providing the greeting. |
| `greeting.name` | string | Name advertised by that node. |
| `greeting.version` | integer | Version ID advertised by that node. |

## Acknowledgement (`-hello`)

| Payload field | Type | Content |
| --- | --- | --- |
| `greeting` | object | Identity of the node acknowledging the exchange. |
| `greeting.node_id` | string | Node ID of the peer providing the greeting. |
| `greeting.name` | string | Name advertised by that node. |
| `greeting.version` | integer | Version ID advertised by that node. |
