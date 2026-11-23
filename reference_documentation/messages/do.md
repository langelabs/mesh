# Do messages

A node sends `do` with a command ID and its positional arguments. The `-do`
reply carries the result or error. Both messages use the
[common envelope](README.md).

## Request (`do`)

| Payload field | Type | Content |
| --- | --- | --- |
| `id` | string | Command ID from the recipient's capability list. |
| `input` | array of base values | Positional arguments in invocation order. Can be empty. |

## Acknowledgement (`-do`)

| Payload field | Type | Content |
| --- | --- | --- |
| `outputs` | array of base values | The Python handler wraps one returned value in a one-element array, including list results. It sends an empty array for no return value or an error. |
| `error` | object or `null` | The Python handler reports `404` for an unknown command ID and `500` for a failed invocation. |
