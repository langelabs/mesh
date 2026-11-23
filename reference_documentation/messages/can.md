# Can messages

A node sends `can` to discover the recipient's registered capabilities. The
`-can` reply describes each capability and its inputs and outputs. Both messages
use the [common envelope](README.md).

## Request (`can`)

| Payload field | Type | Content |
| --- | --- | --- |
| — | — | An empty payload object is valid. |

## Acknowledgement (`-can`)

| Payload field | Type | Content |
| --- | --- | --- |
| `can` | array of objects | Capabilities registered at the responding node. Can be empty. |
| `can[].node` | string | Node ID that advertises the capability. |
| `can[].id` | string | Command ID used in a `do` request. |
| `can[].name` | string | Capability name. |
| `can[].description` | string | Capability description. |
| `can[].input` | array of parameter objects | Ordered input parameters. |
| `can[].output` | array of parameter objects | Output parameters. |
| Parameter `name` | string | Parameter name. |
| Parameter `type` | base value | Type descriptor. The Python implementation advertises annotations as strings. |
| Parameter `description` | string | Parameter description. |
