package mesh

import (
	"bufio"
	"bytes"
	"encoding/json"
	"os"
	"reflect"
	"strings"
	"testing"
)

// TestWireMessages checks all variants against the cross-language fixtures.
func TestWireMessages(t *testing.T) {
	for _, validity := range []string{"valid", "invalid"} {
		t.Run(validity, func(t *testing.T) {
			file, err := os.Open("../../tests/messages-" + validity + ".jsonl")
			if err != nil {
				t.Fatal(err)
			}
			defer file.Close()
			scanner := bufio.NewScanner(file)
			for scanner.Scan() {
				line := scanner.Text()
				message, err := ParseMessage([]byte(line))
				if validity == "invalid" {
					if err == nil {
						t.Errorf("accepted invalid message %s", line)
					}
					continue
				}
				if err != nil {
					t.Fatalf("decode %s: %v", line, err)
				}
				encoded, err := json.Marshal(message)
				if err != nil {
					t.Fatal(err)
				}
				var want, got map[string]any
				for _, item := range []struct {
					reader *json.Decoder
					target *map[string]any
				}{
					{json.NewDecoder(strings.NewReader(line)), &want},
					{json.NewDecoder(bytes.NewReader(encoded)), &got},
				} {
					item.reader.UseNumber()
					if err := item.reader.Decode(item.target); err != nil {
						t.Fatal(err)
					}
				}
				payload := want["payload"].(map[string]any)
				if _, present := payload["error"]; !present {
					payload["error"] = nil
				}
				if !reflect.DeepEqual(want, got) {
					t.Errorf("round trip changed %s into %s", line, encoded)
				}
			}
			if err := scanner.Err(); err != nil {
				t.Fatal(err)
			}
		})
	}
}
