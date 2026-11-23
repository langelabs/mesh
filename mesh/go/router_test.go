package mesh

import (
	"encoding/json"
	"errors"
	"reflect"
	"testing"
)

// dispatch delivers a typed message from a peer to the local router.
func dispatch(t *testing.T, router *Router, payload Payload) RouteOutcome {
	t.Helper()
	outcome, err := router.HandleMessage(Message{Meta: MessageMeta{NodeFrom: "peer", NodeTo: "local"}, Payload: payload})
	if err != nil {
		t.Fatal(err)
	}
	if outcome.Reply != nil {
		want := MessageMeta{Version: 7, NodeFrom: "local", NodeTo: "peer", Hops: List[NodeID]{"local"}}
		if !reflect.DeepEqual(outcome.Reply.Meta, want) {
			t.Fatalf("reply metadata = %+v, want %+v", outcome.Reply.Meta, want)
		}
	}
	return outcome
}

// TestRouterGossip checks greeting and friend discovery state transitions.
func TestRouterGossip(t *testing.T) {
	local := Greeting{NodeID: "local", Name: "Local", Version: 7}
	router := NewRouter(local)
	peer := Greeting{NodeID: "peer", Name: "Peer", Version: 1}
	reply := dispatch(t, router, &HelloPayload{Greeting: peer}).Reply
	if got := reply.Payload.(*HelloAckPayload).Greeting; got != local {
		t.Fatalf("greeting reply = %+v", got)
	}
	ack := &HelloAckPayload{Greeting: Greeting{NodeID: "direct", Name: "Direct", Version: 1}}
	if got := dispatch(t, router, ack).Acknowledgement; got != ack {
		t.Fatal("expected local greeting acknowledgement")
	}
	for _, id := range []NodeID{"peer", "direct"} {
		friend, ok := router.Friend(id)
		if !ok || friend.Distance != 1 || friend.Via != id {
			t.Fatalf("missing direct route to %s: %+v", id, friend)
		}
	}
	initial := &FriendsAckPayload{Friends: List[Friend]{
		{ID: "near", Distance: 3, Via: "peer", Detours: List[NodeID]{"backup"}},
		{ID: "back", Distance: 2, Via: "peer"},
		{ID: "local", Distance: 1, Via: "peer"},
	}}
	if dispatch(t, router, initial).Acknowledgement != initial {
		t.Fatal("expected local friends acknowledgement")
	}
	dispatch(t, router, &FriendsAckPayload{Friends: List[Friend]{
		{ID: "near", Distance: 2, Via: "other", Detours: List[NodeID]{"backup", "other"}},
		{ID: "back", Distance: 2, Via: "other"},
		{ID: "far", Distance: 3, Via: "other"},
	}})
	near, _ := router.Friend("near")
	if near.Via != "other" || near.Distance != 2 || !reflect.DeepEqual(near.Detours, List[NodeID]{"backup", "peer"}) {
		t.Fatalf("shortest route = %+v", near)
	}
	near.Detours[0] = "changed"
	near, _ = router.Friend("near")
	if near.Detours[0] != "backup" {
		t.Fatal("friend snapshot changed routing state")
	}
	back, _ := router.Friend("back")
	if back.Via != "peer" || len(back.Detours) != 1 || back.Detours[0] != "other" {
		t.Fatalf("tied route = %+v", back)
	}
	if _, exists := router.Friend("local"); exists {
		t.Fatal("router learned its own identity as a friend")
	}
	friends := dispatch(t, router, &FriendsPayload{MaxDistance: 3}).Reply.Payload.(*FriendsAckPayload).Friends
	if len(friends) != 2 || friends[0].ID != "direct" || friends[1].ID != "near" ||
		friends[1].Distance != 3 || friends[1].Via != "local" || len(friends[1].Detours) != 0 {
		t.Fatalf("advertised routes = %+v", friends)
	}
}

// TestRouterCapabilities checks discovery, invocation, and local acknowledgements.
func TestRouterCapabilities(t *testing.T) {
	router := NewRouter(Greeting{NodeID: "local", Version: 7})
	group := NewToolGroup("source")
	echo := Capability{ID: "echo", Name: "Echo"}
	group.AddToMesh(echo, func(input []BaseValue) (*BaseValue, error) { return &input[0], nil })
	router.Tools().AddToolGroup(group)
	group.AddToMesh(echo, func([]BaseValue) (*BaseValue, error) { return nil, nil })
	router.Tools().AddToMesh(Capability{ID: "empty"}, func([]BaseValue) (*BaseValue, error) { return nil, nil })
	router.Tools().AddToMesh(Capability{ID: "fail"}, func([]BaseValue) (*BaseValue, error) {
		return nil, errors.New("private details")
	})
	router.Tools().AddToMesh(Capability{ID: "invalid"}, func([]BaseValue) (*BaseValue, error) {
		return &BaseValue{}, nil
	})
	can := dispatch(t, router, &CanPayload{}).Reply.Payload.(*CanAckPayload)
	if len(can.Can) != 4 || can.Can[0].ID != "echo" || can.Can[0].Node != "local" {
		t.Fatalf("capabilities = %+v", can.Can)
	}
	if dispatch(t, router, can).Acknowledgement != can {
		t.Fatal("expected local capability acknowledgement")
	}

	value, err := NewBaseValue([]any{"text", true})
	if err != nil {
		t.Fatal(err)
	}
	for _, test := range []struct {
		id   CmdID
		want string
	}{
		{"echo", `{"error":null,"outputs":[["text",true]]}`},
		{"empty", `{"error":null,"outputs":[]}`},
		{"missing", `{"error":{"code":404,"message":"Unknown capability"},"outputs":[]}`},
		{"fail", `{"error":{"code":500,"message":"Capability invocation failed"},"outputs":[]}`},
		{"invalid", `{"error":{"code":500,"message":"Capability invocation failed"},"outputs":[]}`},
	} {
		t.Run(string(test.id), func(t *testing.T) {
			ack := dispatch(t, router, &DoPayload{ID: test.id, Input: List[BaseValue]{value}}).Reply.Payload.(*DoAckPayload)
			wire, err := json.Marshal(ack)
			if err != nil || string(wire) != test.want {
				t.Fatalf("invocation result = %s, %v, want %s", wire, err, test.want)
			}
			if dispatch(t, router, ack).Acknowledgement != ack {
				t.Fatal("expected local invocation acknowledgement")
			}
		})
	}
}
