use lange_mesh::messages::MeshMsg;
use lange_mesh::router::{AckPayload, MeshRouter, RouteOutcome};
use lange_mesh::tool_group::{MeshToolGroup, ToolResult};
use lange_mesh::types::{Can, Friend, Greeting};
use pollster::block_on;
use serde_json::{Value, json};

/// Create a router with the identity used in the routing tests.
fn router() -> MeshRouter {
    MeshRouter::new(Greeting {
        node_id: "local".into(),
        name: "Local".into(),
        version: 7,
    })
}

/// Decode an incoming message and run it through the public dispatcher.
fn dispatch(router: &mut MeshRouter, sender: &str, kind: &str, payload: Value) -> RouteOutcome {
    let msg = serde_json::from_value::<MeshMsg>(json!({
        "msg": kind,
        "meta": {"version": 1, "node_from": sender, "node_to": "local", "hops": [sender]},
        "payload": payload,
    }))
    .unwrap();
    block_on(router.handle_message(msg))
}

/// Assert reply metadata and return the wire payload for further checks.
fn reply_payload(outcome: RouteOutcome, recipient: &str, kind: &str) -> Value {
    let RouteOutcome::Reply(reply) = outcome else {
        panic!("expected a reply");
    };
    let wire = serde_json::to_value(reply).unwrap();
    assert_eq!(wire["msg"], kind);
    assert_eq!(
        wire["meta"],
        json!({"version": 7, "node_from": "local", "node_to": recipient, "hops": ["local"]})
    );
    wire["payload"].clone()
}

/// Build a capability advertisement whose owner is assigned during registration.
fn capability(id: &str) -> Can {
    Can {
        id: id.into(),
        node: String::new(),
        name: id.into(),
        description: "Test capability".into(),
        input: vec![],
        output: vec![],
    }
}

/// Build a wire route received from a peer.
fn route(id: &str, distance: i64, via: &str, detours: &[&str]) -> Value {
    json!({"id": id, "name": id, "version": 1, "distance": distance, "via": via, "detours": detours})
}

/// Reply to a hello request and learn the sender as directly reachable.
#[test]
fn hello_request_records_peer_and_replies_with_local_identity() {
    let mut router = router();
    let result = dispatch(
        &mut router,
        "peer",
        "hello",
        json!({"greeting": {"node_id": "peer", "name": "Peer", "version": 1}}),
    );
    let payload = reply_payload(result, "peer", "-hello");
    assert_eq!(
        payload["greeting"],
        json!({"node_id": "local", "name": "Local", "version": 7})
    );
    let friend = router.friend("peer").unwrap();
    assert_eq!((friend.distance, friend.via.as_str()), (1, "peer"));
}

/// Record the peer identity carried by a greeting acknowledgement.
#[test]
fn hello_ack_records_peer_and_returns_greeting() {
    let mut router = router();
    let outcome = dispatch(
        &mut router,
        "peer",
        "-hello",
        json!({"greeting": {"node_id": "peer", "name": "Peer", "version": 1}}),
    );
    let RouteOutcome::Acknowledgement(AckPayload::Hello(payload)) = outcome else {
        panic!("expected a greeting payload");
    };
    assert_eq!(payload.greeting.node_id, "peer");
    assert_eq!(router.friend("peer").unwrap().distance, 1);
}

/// Keep the shortest route, preserve the first route on ties, and remember detours.
#[test]
fn friends_ack_merges_routes_and_ignores_the_local_node() {
    let mut router = router();
    dispatch(
        &mut router,
        "peer",
        "-friends",
        json!({"friends": [
            route("a", 3, "peer", &["backup"]),
            route("b", 2, "peer", &[]),
            route("local", 2, "peer", &[]),
        ]}),
    );
    let shorter = route("a", 2, "other", &["backup"]);
    let outcome = dispatch(
        &mut router,
        "other",
        "-friends",
        json!({"friends": [shorter, route("b", 2, "other", &[])]}),
    );
    let RouteOutcome::Acknowledgement(AckPayload::Friends(payload)) = outcome else {
        panic!("expected a friends payload");
    };
    assert_eq!(
        payload.friends[0],
        serde_json::from_value::<Friend>(shorter).unwrap()
    );
    let friend = router.friend("a").unwrap();
    assert_eq!((friend.distance, friend.via.as_str()), (2, "other"));
    assert_eq!(friend.detours, ["backup", "peer"]);
    assert_eq!(router.friend("b").unwrap().via, "peer");
    assert!(router.friend("local").is_none());
}

/// Advertise only routes within the limit that use a different next hop.
#[test]
fn friends_request_rewrites_advertised_routes_without_changing_the_table() {
    let mut router = router();
    dispatch(
        &mut router,
        "peer",
        "-friends",
        json!({"friends": [
            route("near", 2, "peer", &["backup"]),
            route("far", 3, "peer", &[]),
            route("through-requester", 2, "requester", &[]),
        ]}),
    );
    let outcome = dispatch(
        &mut router,
        "requester",
        "friends",
        json!({"max_distance": 3}),
    );
    assert_eq!(
        reply_payload(outcome, "requester", "-friends")["friends"],
        json!([route("near", 3, "local", &[])])
    );
    let friend = router.friend("near").unwrap();
    assert_eq!((friend.distance, friend.via.as_str()), (2, "peer"));
    assert_eq!(friend.detours, ["backup"]);
}

/// Advertise tools copied from nested groups under the receiving node's ID.
#[test]
fn can_request_advertises_group_tools_under_the_router_identity() {
    let mut router = router();
    let mut leaf = MeshToolGroup::new("leaf".into());
    leaf.add_to_mesh(capability("echo"), |input| async move {
        Ok(input.into_iter().next())
    });
    let mut parent = MeshToolGroup::new("parent".into());
    parent.add_tool_group(&leaf);
    router.tools_mut().add_tool_group(&parent);

    let outcome = dispatch(&mut router, "peer", "can", json!({}));
    let payload = reply_payload(outcome, "peer", "-can");
    assert_eq!(
        payload["can"],
        json!([{"id": "echo", "node": "local", "name": "echo", "description": "Test capability", "input": [], "output": []}])
    );
    let outcome = dispatch(
        &mut router,
        "peer",
        "do",
        json!({"id": "echo", "input": ["hello"]}),
    );
    assert_eq!(
        reply_payload(outcome, "peer", "-do")["outputs"],
        json!(["hello"])
    );

    let outcome = dispatch(&mut router, "peer", "-can", payload);
    let RouteOutcome::Acknowledgement(AckPayload::Can(payload)) = outcome else {
        panic!("expected a capability payload");
    };
    assert_eq!(payload.can[0].id, "echo");
}

/// Run an async tool and put its array result in one output slot.
#[test]
fn do_request_preserves_a_list_as_one_result() {
    let mut router = router();
    router
        .tools_mut()
        .add_to_mesh(capability("echo"), |input| async move {
            assert_eq!(input.len(), 2);
            Ok(input.into_iter().nth(1))
        });
    let outcome = dispatch(
        &mut router,
        "peer",
        "do",
        json!({"id": "echo", "input": ["first", [1, 2]]}),
    );
    assert_eq!(
        reply_payload(outcome, "peer", "-do"),
        json!({"outputs": [[1, 2]], "error": null})
    );
}

/// Represent the lack of a tool result with an empty output list.
#[test]
fn do_request_supports_tools_without_an_output() {
    let mut router = router();
    router
        .tools_mut()
        .add_to_mesh(capability("record"), |_| async { Ok(None) });
    let outcome = dispatch(
        &mut router,
        "peer",
        "do",
        json!({"id": "record", "input": []}),
    );
    assert_eq!(
        reply_payload(outcome, "peer", "-do"),
        json!({"outputs": [], "error": null})
    );
}

/// Respond to an unknown command ID with a protocol error.
#[test]
fn do_request_reports_unknown_capabilities() {
    let mut router = router();
    let outcome = dispatch(
        &mut router,
        "peer",
        "do",
        json!({"id": "missing", "input": []}),
    );
    assert_eq!(
        reply_payload(outcome, "peer", "-do"),
        json!({"outputs": [], "error": {"code": 404, "message": "Unknown capability"}})
    );
}

/// Map tool failures to a generic error and expose the decoded acknowledgement.
#[test]
fn do_ack_returns_the_error_payload() {
    let mut router = router();
    router
        .tools_mut()
        .add_to_mesh(capability("fail"), |_| async {
            let result: ToolResult = Err(std::io::Error::other("private details").into());
            result
        });
    let outcome = dispatch(
        &mut router,
        "peer",
        "do",
        json!({"id": "fail", "input": []}),
    );
    let payload = reply_payload(outcome, "peer", "-do");
    assert_eq!(
        payload,
        json!({"outputs": [], "error": {"code": 500, "message": "Capability invocation failed"}})
    );
    let outcome = dispatch(&mut router, "peer", "-do", payload);
    let RouteOutcome::Acknowledgement(AckPayload::Do(payload)) = outcome else {
        panic!("expected an invocation payload");
    };
    assert!(payload.outputs.is_empty());
    assert_eq!(payload.error.unwrap().code, 500);
}
