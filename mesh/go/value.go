package mesh

import (
	"bytes"
	"encoding/json"
	"fmt"
	"maps"
	"math"
	"slices"
)

// BaseValue holds a scalar or a one-level array or object of scalars.
// Use NewBaseValue to construct one. Its zero value cannot be sent.
type BaseValue struct {
	value any
}

// NewBaseValue accepts booleans, strings, finite numbers, and non-nil []any or
// map[string]any containing those scalars. It takes a snapshot of collections.
func NewBaseValue(value any) (BaseValue, error) {
	valid := false
	switch value := value.(type) {
	case []any:
		valid = value != nil && slices.IndexFunc(value, func(v any) bool { return !validScalar(v) }) == -1
	case map[string]any:
		valid = value != nil
		for _, item := range value {
			if !validScalar(item) {
				valid = false
				break
			}
		}
	default:
		valid = validScalar(value)
	}
	if !valid {
		return BaseValue{}, fmt.Errorf("invalid Mesh base value")
	}
	return BaseValue{value: BaseValue{value: value}.Value()}, nil
}

// validScalar checks the native and JSON scalar representations used by BaseValue.
func validScalar(value any) bool {
	switch value := value.(type) {
	case bool, string, int, int8, int16, int32, int64, uint, uint8, uint16, uint32, uint64:
		return true
	case float32:
		return !math.IsNaN(float64(value)) && !math.IsInf(float64(value), 0)
	case float64:
		return !math.IsNaN(value) && !math.IsInf(value, 0)
	case json.Number:
		number, err := value.Float64()
		return err == nil && !math.IsInf(number, 0) && json.Valid([]byte(value))
	default:
		return false
	}
}

// Value returns the scalar or a snapshot of the collection. Decoded numbers use
// json.Number so integers retain their precision.
func (v BaseValue) Value() any {
	switch value := v.value.(type) {
	case []any:
		return slices.Clone(value)
	case map[string]any:
		return maps.Clone(value)
	default:
		return value
	}
}

// MarshalJSON encodes a valid value using its scalar or collection representation.
func (v BaseValue) MarshalJSON() ([]byte, error) {
	if v.value == nil {
		return nil, fmt.Errorf("uninitialized Mesh base value")
	}
	return json.Marshal(v.value)
}

// UnmarshalJSON decodes one Mesh value and rejects null or nested collections.
func (v *BaseValue) UnmarshalJSON(data []byte) error {
	if !json.Valid(data) {
		return fmt.Errorf("invalid Mesh value JSON")
	}
	decoder := json.NewDecoder(bytes.NewReader(data))
	decoder.UseNumber()
	var value any
	if err := decoder.Decode(&value); err != nil {
		return err
	}
	decoded, err := NewBaseValue(value)
	if err != nil {
		return err
	}
	*v = decoded
	return nil
}
