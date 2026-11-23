use std::collections::BTreeMap;

use serde::{Deserialize, Serialize};
use serde_json::Number;

/// A mesh node identifier.
pub type NodeId = String;

/// An identifier for an advertised capability.
pub type CmdId = String;

/// A node protocol version.
pub type VersionId = i64;

/// A scalar on the Mesh wire. Numbers use JSON's finite numeric representation.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum AtomicTypes {
    Number(Number),
    String(String),
    Boolean(bool),
}

/// A scalar, array of scalars, or object with scalar values.
#[derive(Debug, Clone, PartialEq, Serialize, Deserialize)]
#[serde(untagged)]
pub enum BaseTypes {
    Scalar(AtomicTypes),
    Array(Vec<AtomicTypes>),
    Object(BTreeMap<String, AtomicTypes>),
}
