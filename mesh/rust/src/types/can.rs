use serde::{Deserialize, Serialize};

use super::{BaseTypes, CmdId, NodeId};

/// A named input or output parameter of a capability.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CanParameter {
    pub name: String,
    #[serde(rename = "type")]
    pub parameter_type: BaseTypes,
    pub description: String,
}

/// The discovery description of a tool on a node.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct Can {
    pub node: NodeId,
    pub name: String,
    pub description: String,
    pub id: CmdId,
    pub input: Vec<CanParameter>,
    pub output: Vec<CanParameter>,
}
