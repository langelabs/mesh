# Friends messages

A node sends `friends` to discover peers within a maximum hop distance. The
`-friends` reply lists the known routes the recipient advertises. Both messages
use the [common envelope](README.md).

## Request (`friends`)

| Payload field | Type | Content |
| --- | --- | --- |
| `max_distance` | integer | Maximum advertised hop distance from the requester. |

## Acknowledgement (`-friends`)

| Payload field | Type | Content |
| --- | --- | --- |
| `friends` | array of objects | Known peer routes within the requested distance. Can be empty. |
| `friends[].id` | string | Destination peer's node ID. |
| `friends[].name` | string | Name advertised by the destination peer. |
| `friends[].version` | integer | Version ID advertised by the destination peer. |
| `friends[].distance` | integer | Hop count to the destination. |
| `friends[].via` | string | Node ID of the next hop on the primary route. |
| `friends[].detours` | array of strings | Alternate next-hop node IDs. Can be empty. |
