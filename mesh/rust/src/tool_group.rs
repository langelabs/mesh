//! Registration and composition of async mesh capabilities.

use std::{future::Future, pin::Pin, sync::Arc};

use indexmap::IndexMap;

use crate::types::{BaseTypes, Can, CmdId, NodeId};

/// A capability result, with `None` representing an empty output list.
pub type ToolResult = Result<Option<BaseTypes>, Box<dyn std::error::Error + Send + Sync>>;

type ToolFuture = Pin<Box<dyn Future<Output = ToolResult> + Send>>;
type ToolHandler = Arc<dyn Fn(Vec<BaseTypes>) -> ToolFuture + Send + Sync>;

/// A discovery description paired with the callable that implements it.
#[derive(Clone)]
pub(crate) struct RegisteredTool {
    pub(crate) capability: Can,
    pub(crate) handler: ToolHandler,
}

/// A set of capabilities advertised under a common owner ID.
pub struct MeshToolGroup {
    node_id: NodeId,
    pub(crate) registered: IndexMap<CmdId, RegisteredTool>,
}

impl MeshToolGroup {
    /// Create an empty group for the given owner ID.
    pub fn new(node_id: NodeId) -> Self {
        Self {
            node_id,
            registered: IndexMap::new(),
        }
    }

    /// Register a tool with explicit discovery metadata and replace any matching ID.
    pub fn add_to_mesh<F, Fut>(&mut self, mut capability: Can, handler: F)
    where
        F: Fn(Vec<BaseTypes>) -> Fut + Send + Sync + 'static,
        Fut: Future<Output = ToolResult> + Send + 'static,
    {
        capability.node.clone_from(&self.node_id);
        self.registered.insert(
            capability.id.clone(),
            RegisteredTool {
                capability,
                handler: Arc::new(move |inputs| Box::pin(handler(inputs))),
            },
        );
    }

    /// Copy a group's current tools under this group's owner ID and replace matching entries.
    pub fn add_tool_group(&mut self, group: &Self) {
        self.registered
            .extend(group.registered.iter().map(|(id, tool)| {
                let mut tool = tool.clone();
                tool.capability.node.clone_from(&self.node_id);
                (id.clone(), tool)
            }));
    }
}
