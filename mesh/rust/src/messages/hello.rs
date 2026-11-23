use serde::{Deserialize, Serialize};

use crate::types::{Error, Greeting};

/// The node identity exchanged in both greeting directions.
#[derive(Debug, Clone, PartialEq, Eq, Serialize, Deserialize)]
pub struct HelloPayload {
    pub greeting: Greeting,
    pub error: Option<Error>,
}
