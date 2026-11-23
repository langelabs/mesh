use serde::{Deserialize, Serialize};

use crate::types::{BaseTypes, CmdId, Error};

/// A command ID and its ordered arguments.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DoPayload {
    pub id: CmdId,
    pub input: Vec<BaseTypes>,
    pub error: Option<Error>,
}

/// The result or error of a command invocation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
pub struct DoAckPayload {
    pub outputs: Vec<BaseTypes>,
    pub error: Option<Error>,
}
