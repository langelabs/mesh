// Package mesh implements Mesh wire messages and local routing.
package mesh

import (
	"bytes"
	"encoding/json"
	"fmt"
)

// NodeID identifies a mesh node.
type NodeID string

// UnmarshalJSON decodes a node ID and requires a JSON string.
func (id *NodeID) UnmarshalJSON(data []byte) error {
	if bytes.Equal(data, []byte("null")) {
		return fmt.Errorf("node ID must be a string")
	}
	return json.Unmarshal(data, (*string)(id))
}

// CmdID identifies an advertised capability.
type CmdID string

// VersionID is a node's advertised protocol version.
type VersionID int64

// List is a required wire array whose zero value encodes as an empty array.
type List[T any] []T

// MarshalJSON encodes the list as an array, including when the slice is nil.
func (list List[T]) MarshalJSON() ([]byte, error) {
	if list == nil {
		return []byte("[]"), nil
	}
	return json.Marshal([]T(list))
}

// MeshError carries protocol error details.
type MeshError struct {
	Code    int64  `json:"code"`
	Message string `json:"message"`
}

// UnmarshalJSON requires both error fields.
func (e *MeshError) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{"code": &e.Code, "message": &e.Message}, nil)
}

// Greeting is the identity and version a node advertises.
type Greeting struct {
	NodeID  NodeID    `json:"node_id"`
	Name    string    `json:"name"`
	Version VersionID `json:"version"`
}

// UnmarshalJSON requires all greeting fields.
func (g *Greeting) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{"node_id": &g.NodeID, "name": &g.Name, "version": &g.Version}, nil)
}

// Friend describes the known route and alternate next hops to a peer.
type Friend struct {
	ID       NodeID       `json:"id"`
	Name     string       `json:"name"`
	Version  VersionID    `json:"version"`
	Distance int64        `json:"distance"`
	Via      NodeID       `json:"via"`
	Detours  List[NodeID] `json:"detours"`
}

// UnmarshalJSON requires all route fields.
func (f *Friend) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{
		"id": &f.ID, "name": &f.Name, "version": &f.Version, "distance": &f.Distance,
		"via": &f.Via, "detours": &f.Detours,
	}, nil)
}

// Parameter describes an input or output of a capability.
type Parameter struct {
	Name        string    `json:"name"`
	Type        BaseValue `json:"type"`
	Description string    `json:"description"`
}

// UnmarshalJSON requires all parameter fields.
func (p *Parameter) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{"name": &p.Name, "type": &p.Type, "description": &p.Description}, nil)
}

// Capability is a tool's advertised discovery description.
type Capability struct {
	Node        NodeID          `json:"node"`
	ID          CmdID           `json:"id"`
	Name        string          `json:"name"`
	Description string          `json:"description"`
	Input       List[Parameter] `json:"input"`
	Output      List[Parameter] `json:"output"`
}

// UnmarshalJSON requires all capability fields.
func (c *Capability) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{
		"node": &c.Node, "id": &c.ID, "name": &c.Name, "description": &c.Description,
		"input": &c.Input, "output": &c.Output,
	}, nil)
}
