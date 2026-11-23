use serde::{Deserialize, Serialize};

use crate::types::{Error, Friend};

/// The maximum requested distance for an advertised route.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FriendsPayload {
    pub max_distance: i64,
    pub error: Option<Error>,
}

/// Routes advertised by the responding node.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct FriendsAckPayload {
    pub friends: Vec<Friend>,
    pub error: Option<Error>,
}
