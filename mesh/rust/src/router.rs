//! Dispatch requests and acknowledgements for a local Mesh node.

use indexmap::{IndexMap, IndexSet, map::Entry};

use crate::{
    messages::{
        CanAckPayload, DoAckPayload, FriendsAckPayload, HelloPayload, MeshMsg, MeshMsgEnvelope,
        MeshMsgMeta,
    },
    tool_group::MeshToolGroup,
    types::{Error, Friend, Greeting, NodeId},
};

/// The typed payload returned locally when the router receives an acknowledgement.
#[derive(Debug, Clone, PartialEq)]
pub enum AckPayload {
    Hello(HelloPayload),
    Friends(FriendsAckPayload),
    Can(CanAckPayload),
    Do(DoAckPayload),
}

/// The result of processing an inbound message.
#[derive(Debug, Clone, PartialEq)]
pub enum RouteOutcome {
    /// An acknowledgement to send back to the requester.
    Reply(MeshMsg),
    /// An acknowledgement payload to deliver to the local caller.
    Acknowledgement(AckPayload),
}

/// A node's identity, advertised capabilities, and known peer routes.
pub struct MeshRouter {
    identity: Greeting,
    tools: MeshToolGroup,
    friends: IndexMap<NodeId, Friend>,
}

impl MeshRouter {
    /// Create a router using the supplied local identity.
    pub fn new(identity: Greeting) -> Self {
        Self {
            tools: MeshToolGroup::new(identity.node_id.clone()),
            identity,
            friends: IndexMap::new(),
        }
    }

    /// Access the local tool group to register or include capabilities.
    pub fn tools_mut(&mut self) -> &mut MeshToolGroup {
        &mut self.tools
    }

    /// Return the known route to a node, if one has been learned.
    pub fn friend(&self, node_id: &str) -> Option<&Friend> {
        self.friends.get(node_id)
    }

    /// Process a message delivered to this node and return its reply or acknowledgement payload.
    pub async fn handle_message(&mut self, message: MeshMsg) -> RouteOutcome {
        match message {
            MeshMsg::Hello(MeshMsgEnvelope { meta, payload }) => {
                self.merge_greeting(&payload.greeting);
                RouteOutcome::Reply(MeshMsg::HelloAck(MeshMsgEnvelope {
                    meta: self.reply_meta(meta.node_from),
                    payload: HelloPayload {
                        greeting: self.identity.clone(),
                        error: None,
                    },
                }))
            }
            MeshMsg::HelloAck(message) => {
                self.merge_greeting(&message.payload.greeting);
                RouteOutcome::Acknowledgement(AckPayload::Hello(message.payload))
            }
            MeshMsg::Friends(MeshMsgEnvelope { meta, payload }) => {
                let requester = meta.node_from;
                let friends = self
                    .friends
                    .values()
                    .filter(|friend| {
                        friend.distance < payload.max_distance && friend.via != requester
                    })
                    .map(|friend| Friend {
                        id: friend.id.clone(),
                        name: friend.name.clone(),
                        version: friend.version,
                        distance: friend.distance + 1,
                        via: self.identity.node_id.clone(),
                        detours: Vec::new(),
                    })
                    .collect();
                RouteOutcome::Reply(MeshMsg::FriendsAck(MeshMsgEnvelope {
                    meta: self.reply_meta(requester),
                    payload: FriendsAckPayload {
                        friends,
                        error: None,
                    },
                }))
            }
            MeshMsg::FriendsAck(message) => {
                self.merge_friends(message.payload.friends.iter().cloned());
                RouteOutcome::Acknowledgement(AckPayload::Friends(message.payload))
            }
            MeshMsg::Can(message) => RouteOutcome::Reply(MeshMsg::CanAck(MeshMsgEnvelope {
                meta: self.reply_meta(message.meta.node_from),
                payload: CanAckPayload {
                    can: self
                        .tools
                        .registered
                        .values()
                        .map(|tool| tool.capability.clone())
                        .collect(),
                    error: None,
                },
            })),
            MeshMsg::CanAck(message) => {
                RouteOutcome::Acknowledgement(AckPayload::Can(message.payload))
            }
            MeshMsg::Do(MeshMsgEnvelope { meta, payload }) => {
                let result = match self.tools.registered.get(&payload.id) {
                    Some(tool) => (tool.handler)(payload.input).await.map_err(|_| Error {
                        code: 500,
                        message: "Capability invocation failed".into(),
                    }),
                    None => Err(Error {
                        code: 404,
                        message: "Unknown capability".into(),
                    }),
                };
                let payload = match result {
                    Ok(output) => DoAckPayload {
                        outputs: output.into_iter().collect(),
                        error: None,
                    },
                    Err(error) => DoAckPayload {
                        outputs: Vec::new(),
                        error: Some(error),
                    },
                };
                RouteOutcome::Reply(MeshMsg::DoAck(MeshMsgEnvelope {
                    meta: self.reply_meta(meta.node_from),
                    payload,
                }))
            }
            MeshMsg::DoAck(message) => {
                RouteOutcome::Acknowledgement(AckPayload::Do(message.payload))
            }
        }
    }

    /// Address a reply to the original sender and start its path at this node.
    fn reply_meta(&self, recipient: NodeId) -> MeshMsgMeta {
        MeshMsgMeta {
            version: self.identity.version,
            node_from: self.identity.node_id.clone(),
            node_to: recipient,
            hops: vec![self.identity.node_id.clone()],
        }
    }

    /// Learn a direct one-hop route from a greeting.
    fn merge_greeting(&mut self, greeting: &Greeting) {
        self.merge_friends([Friend {
            id: greeting.node_id.clone(),
            name: greeting.name.clone(),
            version: greeting.version,
            distance: 1,
            via: greeting.node_id.clone(),
            detours: Vec::new(),
        }]);
    }

    /// Retain the shortest primary route and merge alternate next hops in order.
    fn merge_friends(&mut self, incoming: impl IntoIterator<Item = Friend>) {
        for mut alternate in incoming {
            if alternate.id == self.identity.node_id {
                continue;
            }

            match self.friends.entry(alternate.id.clone()) {
                Entry::Vacant(entry) => {
                    entry.insert(alternate);
                }
                Entry::Occupied(mut entry) => {
                    let primary = entry.get_mut();
                    if alternate.distance < primary.distance {
                        std::mem::swap(primary, &mut alternate);
                    }

                    let mut detours: IndexSet<_> = std::mem::take(&mut primary.detours)
                        .into_iter()
                        .chain([alternate.via])
                        .chain(alternate.detours)
                        .collect();
                    detours.shift_remove(&primary.via);
                    primary.detours = detours.into_iter().collect();
                }
            }
        }
    }
}
