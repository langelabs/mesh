//! Message envelopes and payloads for the Mesh protocol.

mod base;
mod can;
mod do_message;
mod friends;
mod hello;

pub use base::{MeshMsgEnvelope, MeshMsgMeta};
pub use can::{CanAckPayload, CanPayload};
pub use do_message::{DoAckPayload, DoPayload};
pub use friends::{FriendsAckPayload, FriendsPayload};
pub use hello::HelloPayload;

use serde::{Deserialize, Serialize};

/// A request or acknowledgement dispatched by the wire `msg` field.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(tag = "msg")]
pub enum MeshMsg {
    #[serde(rename = "hello")]
    Hello(MeshMsgEnvelope<HelloPayload>),
    #[serde(rename = "-hello")]
    HelloAck(MeshMsgEnvelope<HelloPayload>),
    #[serde(rename = "friends")]
    Friends(MeshMsgEnvelope<FriendsPayload>),
    #[serde(rename = "-friends")]
    FriendsAck(MeshMsgEnvelope<FriendsAckPayload>),
    #[serde(rename = "can")]
    Can(MeshMsgEnvelope<CanPayload>),
    #[serde(rename = "-can")]
    CanAck(MeshMsgEnvelope<CanAckPayload>),
    #[serde(rename = "do")]
    Do(MeshMsgEnvelope<DoPayload>),
    #[serde(rename = "-do")]
    DoAck(MeshMsgEnvelope<DoAckPayload>),
}
