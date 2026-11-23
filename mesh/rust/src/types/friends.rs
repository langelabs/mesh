use serde::{Deserialize, Serialize};

use super::{NodeId, VersionId};

/// A known node and the available next hops to reach it.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct Friend {
    pub id: NodeId,
    pub name: String,
    pub version: VersionId,
    pub distance: i64,
    pub via: NodeId,
    pub detours: Vec<NodeId>,
}
