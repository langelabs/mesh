package mesh

import (
	"bytes"
	"encoding/json"
	"fmt"
)

// MessageMeta carries the sender, destination, version, and path of a message.
type MessageMeta struct {
	Version  VersionID    `json:"version"`
	NodeFrom NodeID       `json:"node_from"`
	NodeTo   NodeID       `json:"node_to"`
	Hops     List[NodeID] `json:"hops"`
}

// UnmarshalJSON requires all metadata fields.
func (m *MessageMeta) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{
		"version": &m.Version, "node_from": &m.NodeFrom, "node_to": &m.NodeTo, "hops": &m.Hops,
	}, nil)
}

// Payload is one of the eight concrete Mesh request or acknowledgement payloads.
// Use a pointer to the concrete payload when constructing a Message.
type Payload interface {
	meshPayload()
}

// Acknowledgement is a payload delivered to the local caller after a reply arrives.
type Acknowledgement interface {
	Payload
	meshAcknowledgement()
}

// PayloadError carries the optional error shared by all payloads.
type PayloadError struct {
	Error *MeshError `json:"error"`
}

// meshPayload marks the payload types that embed PayloadError.
func (PayloadError) meshPayload() {}

// HelloPayload exchanges the initiating node's identity.
type HelloPayload struct {
	PayloadError
	Greeting Greeting `json:"greeting"`
}

// UnmarshalJSON decodes a greeting request.
func (p *HelloPayload) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{"greeting": &p.Greeting}, &p.Error)
}

// HelloAckPayload carries the responding node's identity.
type HelloAckPayload HelloPayload

// meshPayload marks a greeting acknowledgement as a Mesh payload.
func (*HelloAckPayload) meshPayload() {}

// meshAcknowledgement marks a greeting acknowledgement.
func (*HelloAckPayload) meshAcknowledgement() {}

// UnmarshalJSON decodes the shared greeting shape.
func (p *HelloAckPayload) UnmarshalJSON(data []byte) error {
	return (*HelloPayload)(p).UnmarshalJSON(data)
}

// FriendsPayload requests routes within a maximum distance.
type FriendsPayload struct {
	PayloadError
	MaxDistance int64 `json:"max_distance"`
}

// UnmarshalJSON decodes a friend discovery request.
func (p *FriendsPayload) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{"max_distance": &p.MaxDistance}, &p.Error)
}

// FriendsAckPayload advertises known routes.
type FriendsAckPayload struct {
	PayloadError
	Friends List[Friend] `json:"friends"`
}

// meshAcknowledgement marks a route discovery acknowledgement.
func (*FriendsAckPayload) meshAcknowledgement() {}

// UnmarshalJSON decodes advertised routes.
func (p *FriendsAckPayload) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{"friends": &p.Friends}, &p.Error)
}

// CanPayload requests a node's capability descriptions.
type CanPayload struct {
	PayloadError
}

// UnmarshalJSON decodes a capability discovery request.
func (p *CanPayload) UnmarshalJSON(data []byte) error {
	return decodeFields(data, nil, &p.Error)
}

// CanAckPayload advertises a node's capabilities.
type CanAckPayload struct {
	PayloadError
	Can List[Capability] `json:"can"`
}

// meshAcknowledgement marks a capability discovery acknowledgement.
func (*CanAckPayload) meshAcknowledgement() {}

// UnmarshalJSON decodes advertised capabilities.
func (p *CanAckPayload) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{"can": &p.Can}, &p.Error)
}

// DoPayload invokes a capability with positional input values.
type DoPayload struct {
	PayloadError
	ID    CmdID           `json:"id"`
	Input List[BaseValue] `json:"input"`
}

// UnmarshalJSON decodes a capability invocation.
func (p *DoPayload) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{"id": &p.ID, "input": &p.Input}, &p.Error)
}

// DoAckPayload carries an invocation's outputs or protocol error.
type DoAckPayload struct {
	PayloadError
	Outputs List[BaseValue] `json:"outputs"`
}

// meshAcknowledgement marks a capability invocation acknowledgement.
func (*DoAckPayload) meshAcknowledgement() {}

// UnmarshalJSON decodes capability outputs.
func (p *DoAckPayload) UnmarshalJSON(data []byte) error {
	return decodeFields(data, fields{"outputs": &p.Outputs}, &p.Error)
}

// Message is the common Mesh envelope. The concrete payload determines its wire name.
type Message struct {
	Meta    MessageMeta
	Payload Payload
}

// Kind returns the payload's wire name, or an empty string for an invalid payload.
func (m Message) Kind() string {
	var kind string
	var valid bool
	switch p := m.Payload.(type) {
	case *HelloPayload:
		kind, valid = "hello", p != nil
	case *HelloAckPayload:
		kind, valid = "-hello", p != nil
	case *FriendsPayload:
		kind, valid = "friends", p != nil
	case *FriendsAckPayload:
		kind, valid = "-friends", p != nil
	case *CanPayload:
		kind, valid = "can", p != nil
	case *CanAckPayload:
		kind, valid = "-can", p != nil
	case *DoPayload:
		kind, valid = "do", p != nil
	case *DoAckPayload:
		kind, valid = "-do", p != nil
	}
	if valid {
		return kind
	}
	return ""
}

// MarshalJSON encodes the metadata and the payload under its wire discriminator.
func (m Message) MarshalJSON() ([]byte, error) {
	kind := m.Kind()
	if kind == "" {
		return nil, fmt.Errorf("invalid Mesh message payload %T", m.Payload)
	}
	return json.Marshal(struct {
		Kind    string      `json:"msg"`
		Meta    MessageMeta `json:"meta"`
		Payload Payload     `json:"payload"`
	}{kind, m.Meta, m.Payload})
}

// UnmarshalJSON decodes the envelope and validates the payload for its wire name.
func (m *Message) UnmarshalJSON(data []byte) error {
	var decoded Message
	var kind string
	var payload json.RawMessage
	if err := decodeFields(data, fields{"msg": &kind, "meta": &decoded.Meta, "payload": &payload}, nil); err != nil {
		return err
	}
	switch kind {
	case "hello":
		decoded.Payload = &HelloPayload{}
	case "-hello":
		decoded.Payload = &HelloAckPayload{}
	case "friends":
		decoded.Payload = &FriendsPayload{}
	case "-friends":
		decoded.Payload = &FriendsAckPayload{}
	case "can":
		decoded.Payload = &CanPayload{}
	case "-can":
		decoded.Payload = &CanAckPayload{}
	case "do":
		decoded.Payload = &DoPayload{}
	case "-do":
		decoded.Payload = &DoAckPayload{}
	default:
		return fmt.Errorf("unknown Mesh message type %q", kind)
	}
	if err := json.Unmarshal(payload, decoded.Payload); err != nil {
		return fmt.Errorf("invalid %s payload: %w", kind, err)
	}
	*m = decoded
	return nil
}

// ParseMessage decodes and validates a JSON Mesh message.
func ParseMessage(data []byte) (Message, error) {
	var message Message
	err := json.Unmarshal(data, &message)
	return message, err
}

type fields map[string]any

// decodeFields decodes the required non-null fields and the optional payload error.
func decodeFields(data []byte, required fields, payloadError **MeshError) error {
	var object map[string]json.RawMessage
	if err := json.Unmarshal(data, &object); err != nil {
		return err
	}
	if object == nil {
		return fmt.Errorf("expected a Mesh object")
	}
	for key, target := range required {
		raw := object[key]
		if raw == nil || bytes.Equal(raw, []byte("null")) {
			return fmt.Errorf("missing or null Mesh field %q", key)
		}
		if err := json.Unmarshal(raw, target); err != nil {
			return fmt.Errorf("invalid Mesh field %q: %w", key, err)
		}
	}
	if payloadError != nil {
		*payloadError = nil
		if raw := object["error"]; raw != nil {
			if err := json.Unmarshal(raw, payloadError); err != nil {
				return fmt.Errorf("invalid Mesh payload error: %w", err)
			}
		}
	}
	return nil
}
