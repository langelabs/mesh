package mesh

import (
	"fmt"
	"slices"
	"sync"
)

// RouteOutcome contains either a reply to send or an acknowledgement to deliver locally.
type RouteOutcome struct {
	Reply           *Message
	Acknowledgement Acknowledgement
}

// Router holds a local identity, registered capabilities, and known peer routes.
// Its methods are safe for concurrent use. Do not copy a Router after first use.
type Router struct {
	identity Greeting
	tools    *ToolGroup

	mu      sync.RWMutex
	friends []Friend
	index   map[NodeID]int
}

// NewRouter creates a local router using the supplied identity.
func NewRouter(identity Greeting) *Router {
	return &Router{identity: identity, tools: NewToolGroup(identity.NodeID), index: make(map[NodeID]int)}
}

// Tools returns the router's local capability group.
func (r *Router) Tools() *ToolGroup {
	return r.tools
}

// Friend returns a snapshot of a known route.
func (r *Router) Friend(id NodeID) (Friend, bool) {
	r.mu.RLock()
	defer r.mu.RUnlock()
	index, exists := r.index[id]
	if !exists {
		return Friend{}, false
	}
	friend := r.friends[index]
	friend.Detours = slices.Clone(friend.Detours)
	return friend, true
}

// HandleMessage dispatches a message already delivered to this router.
func (r *Router) HandleMessage(message Message) (RouteOutcome, error) {
	if message.Kind() == "" {
		return RouteOutcome{}, fmt.Errorf("invalid Mesh message payload %T", message.Payload)
	}
	// Address replies to the original sender and start their path at this node.
	reply := func(payload Payload) (RouteOutcome, error) {
		return RouteOutcome{Reply: &Message{
			Meta: MessageMeta{
				Version: r.identity.Version, NodeFrom: r.identity.NodeID,
				NodeTo: message.Meta.NodeFrom, Hops: List[NodeID]{r.identity.NodeID},
			},
			Payload: payload,
		}}, nil
	}

	switch payload := message.Payload.(type) {
	case *HelloPayload:
		r.mergeGreeting(payload.Greeting)
		return reply(&HelloAckPayload{Greeting: r.identity})
	case *HelloAckPayload:
		r.mergeGreeting(payload.Greeting)
		return RouteOutcome{Acknowledgement: payload}, nil
	case *FriendsPayload:
		r.mu.RLock()
		var friends List[Friend]
		for _, friend := range r.friends {
			if friend.Distance < payload.MaxDistance && friend.Via != message.Meta.NodeFrom {
				friend.Distance++
				friend.Via = r.identity.NodeID
				friend.Detours = nil
				friends = append(friends, friend)
			}
		}
		r.mu.RUnlock()
		return reply(&FriendsAckPayload{Friends: friends})
	case *FriendsAckPayload:
		r.mergeFriends(payload.Friends)
		return RouteOutcome{Acknowledgement: payload}, nil
	case *CanPayload:
		return reply(&CanAckPayload{Can: r.tools.Capabilities()})
	case *DoPayload:
		result := r.tools.Invoke(payload.ID, slices.Clone(payload.Input))
		return reply(&result)
	case Acknowledgement:
		return RouteOutcome{Acknowledgement: payload}, nil
	}
	return RouteOutcome{}, fmt.Errorf("invalid Mesh message payload %T", message.Payload)
}

// mergeGreeting records the direct route learned from either greeting direction.
func (r *Router) mergeGreeting(greeting Greeting) {
	r.mergeFriends([]Friend{{
		ID: greeting.NodeID, Name: greeting.Name, Version: greeting.Version,
		Distance: 1, Via: greeting.NodeID,
	}})
}

// mergeFriends retains the shortest route and records alternate next hops in discovery order.
func (r *Router) mergeFriends(incoming []Friend) {
	r.mu.Lock()
	defer r.mu.Unlock()
	for _, alternate := range incoming {
		if alternate.ID == r.identity.NodeID {
			continue
		}
		index, exists := r.index[alternate.ID]
		if !exists {
			alternate.Detours = slices.Clone(alternate.Detours)
			r.index[alternate.ID] = len(r.friends)
			r.friends = append(r.friends, alternate)
			continue
		}

		primary := r.friends[index]
		if alternate.Distance < primary.Distance {
			primary, alternate = alternate, primary
		}
		detours := make(List[NodeID], 0, len(primary.Detours)+1+len(alternate.Detours))
		seen := map[NodeID]bool{primary.Via: true}
		for _, group := range [][]NodeID{primary.Detours, {alternate.Via}, alternate.Detours} {
			for _, via := range group {
				if !seen[via] {
					seen[via] = true
					detours = append(detours, via)
				}
			}
		}
		primary.Detours = detours
		r.friends[index] = primary
	}
}
