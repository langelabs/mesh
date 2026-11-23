use serde::{Deserialize, Serialize};

use super::{NodeId, VersionId};

/// The identity and version advertised by a node.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Greeting {
    pub node_id: NodeId,
    pub name: String,
    pub version: VersionId,
}
