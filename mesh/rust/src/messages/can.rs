use serde::{Deserialize, Serialize};

use crate::types::{Can, Error};

/// A request for the recipient's capability descriptions.
#[derive(Debug, Clone, Default, PartialEq, Eq, Serialize, Deserialize)]
pub struct CanPayload {
    pub error: Option<Error>,
}

/// Capability descriptions from the responding node.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct CanAckPayload {
    pub can: Vec<Can>,
    pub error: Option<Error>,
}
