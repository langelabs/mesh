# Lange Mesh for Go

This reference implementation provides [Mesh wire messages](../../reference_documentation/messages/README.md), peer discovery, and local capability dispatch. It uses Go 1.23 or later and the standard library.

Run `go test -race ./...` from this directory. To use the module from a local application, add a replacement for `github.com/langelabs/mesh` pointing to this directory.

```sh
go mod edit -replace=github.com/langelabs/mesh=/path/to/mesh/mesh/go
go get github.com/langelabs/mesh
```

```go
package main

import (
	"encoding/json"
	"fmt"
	"log"

	"github.com/langelabs/mesh"
)

func main() {
	router := mesh.NewRouter(mesh.Greeting{NodeID: "local", Name: "Local", Version: 1})
	text, err := mesh.NewBaseValue("string")
	if err != nil {
		log.Fatal(err)
	}
	parameter := mesh.Parameter{Name: "value", Type: text, Description: "The value to echo."}
	router.Tools().AddToMesh(mesh.Capability{
		ID: "echo", Name: "Echo", Description: "Returns the supplied value.",
		Input: mesh.List[mesh.Parameter]{parameter}, Output: mesh.List[mesh.Parameter]{parameter},
	}, func(input []mesh.BaseValue) (*mesh.BaseValue, error) {
		if len(input) != 1 {
			return nil, fmt.Errorf("expected one input")
		}
		return &input[0], nil
	})

	message, err := mesh.ParseMessage([]byte(`{
		"msg":"do",
		"meta":{"version":1,"node_from":"peer","node_to":"local","hops":["peer"]},
		"payload":{"id":"echo","input":["hello"]}
	}`))
	if err != nil {
		log.Fatal(err)
	}

	outcome, err := router.HandleMessage(message)
	if err != nil {
		log.Fatal(err)
	}
	if outcome.Reply != nil {
		data, err := json.Marshal(outcome.Reply)
		if err != nil {
			log.Fatal(err)
		}
		fmt.Println(string(data))
	}
}
```

Pass each inbound message through `ParseMessage`. A request returns a typed reply envelope that can be encoded with `json.Marshal`. A received acknowledgement exposes its concrete payload on `RouteOutcome.Acknowledgement`.

Handlers run in the calling goroutine and may be invoked concurrently. A nil result with no error produces an empty output list. Each other successful result occupies one output slot, including array and object values. Protocol integer fields are signed 64-bit values. Decoded numbers in base values are available as `json.Number`.
