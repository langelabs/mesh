use lange_mesh::messages::MeshMsg;
use serde_json::{Value, json};

/// Match the Python envelope and payload fields for every message type.
#[test]
fn round_trips_all_wire_messages() {
    let greeting = json!({"node_id": "peer", "name": "Peer", "version": 1});
    let friend = json!({
        "id": "friend", "name": "Friend", "version": 1,
        "distance": 2, "via": "peer", "detours": ["other"],
    });
    let parameter = json!({"name": "text", "type": "str", "description": "Input"});
    let capability = json!({
        "node": "peer", "id": "echo", "name": "Echo", "description": "Echoes a value",
        "input": [parameter], "output": [],
    });

    for (kind, payload) in [
        ("hello", json!({"greeting": greeting})),
        ("-hello", json!({"greeting": greeting})),
        ("friends", json!({"max_distance": 3})),
        ("-friends", json!({"friends": [friend]})),
        ("can", json!({})),
        ("-can", json!({"can": [capability]})),
        (
            "do",
            json!({"id": "echo", "input": [1, 1.25, "text", true, ["a", 2], {"ready": false}]}),
        ),
        ("-do", json!({"outputs": [["a", 2]]})),
        (
            "-do",
            json!({"outputs": [], "error": {"code": 404, "message": "Unknown capability"}}),
        ),
    ] {
        let mut wire = json!({
            "msg": kind,
            "meta": {"version": 1, "node_from": "peer", "node_to": "local", "hops": ["peer"]},
            "payload": payload,
        });
        let parsed: MeshMsg = serde_json::from_str(&wire.to_string()).unwrap();
        if wire["payload"].get("error").is_none() {
            wire["payload"]["error"] = Value::Null;
        }
        assert_eq!(serde_json::to_value(parsed).unwrap(), wire, "{kind}");
    }
}

/// Reject messages whose discriminator, envelope, or typed payload is invalid.
#[test]
fn rejects_invalid_wire_messages() {
    for (kind, payload) in [
        ("ping", json!({})),
        ("hello", json!({})),
        ("-can", json!({"can": null})),
        ("do", json!({"id": "echo", "input": [[["nested"]]]})),
        ("do", json!({"id": "echo", "input": [{"nested": [1]}]})),
        ("do", json!({"id": "echo", "input": [null]})),
        ("can", json!({"error": {"code": 500}})),
    ] {
        let wire = json!({
            "msg": kind,
            "meta": {"version": 1, "node_from": "peer", "node_to": "local", "hops": ["peer"]},
            "payload": payload,
        });
        assert!(serde_json::from_value::<MeshMsg>(wire).is_err(), "{kind}");
    }

    assert!(serde_json::from_value::<MeshMsg>(json!({"msg": "can", "payload": {}})).is_err());
}
