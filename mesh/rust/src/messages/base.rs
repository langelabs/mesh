use serde::{Deserialize, Serialize};

use crate::types::{NodeId, VersionId};

/// The sender, destination, version, and path shared by all messages.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MeshMsgMeta {
    pub version: VersionId,
    pub node_from: NodeId,
    pub node_to: NodeId,
    pub hops: Vec<NodeId>,
}

/// The metadata and typed payload carried by a message variant.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct MeshMsgEnvelope<Payload> {
    pub meta: MeshMsgMeta,
    pub payload: Payload,
}
