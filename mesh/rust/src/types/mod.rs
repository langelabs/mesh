//! Shared protocol types used by the message payloads.

mod can;
mod common;
mod error;
mod friends;
mod greeting;

pub use can::{Can, CanParameter};
pub use common::{AtomicTypes, BaseTypes, CmdId, NodeId, VersionId};
pub use error::Error;
pub use friends::Friend;
pub use greeting::Greeting;
