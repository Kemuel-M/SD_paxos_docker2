"""
Message structure definitions for the Paxos protocol.
"""

import time
import uuid
from dataclasses import dataclass, asdict, field
from typing import Dict, List, Any, Optional, Union


def generate_tid():
    """Generate a unique transaction ID."""
    return str(uuid.uuid4())


@dataclass
class Message:
    """Base class for all messages."""
    type: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class PrepareMessage(Message):
    """Prepare message from Proposer to Acceptor."""
    proposal_number: int
    proposer_id: str


@dataclass
class AcceptMessage(Message):
    """Accept message from Proposer to Acceptor."""
    proposal_number: int
    value: Any
    proposer_id: str


@dataclass
class HeartbeatMessage(Message):
    """Heartbeat message from Leader to all nodes."""
    leader_id: str
    sequence_number: int
    timestamp: float


@dataclass
class PromiseMessage(Message):
    """Promise message from Acceptor to Proposer."""
    proposal_number: int
    accepted_proposal: Optional[int] = None
    accepted_value: Optional[Any] = None
    tid: str = field(default_factory=generate_tid)


@dataclass
class NotPromiseMessage(Message):
    """Not Promise message from Acceptor to Proposer."""
    promised_proposal: int
    tid: str = field(default_factory=generate_tid)


@dataclass
class AcceptedMessage(Message):
    """Accepted message from Acceptor to Proposer."""
    proposal_number: int
    value: Any
    tid: str = field(default_factory=generate_tid)


@dataclass
class NotAcceptedMessage(Message):
    """Not Accepted message from Acceptor to Proposer."""
    promised_proposal: int
    tid: str = field(default_factory=generate_tid)


@dataclass
class LearnMessage(Message):
    """Learn message from Acceptor to Learner."""
    proposal_number: int
    value: Any
    acceptor_id: str
    tid: str


@dataclass
class SyncRequestMessage(Message):
    """Sync request message between Learners."""
    from_seq: int
    to_seq: int
    learner_id: str


@dataclass
class SyncResponseMessage(Message):
    """Sync response message between Learners."""
    decisions: List[Dict[str, Any]]
    learner_id: str


@dataclass
class WriteRequestMessage(Message):
    """Write request message from Client to Proposer."""
    request_id: str
    client_id: str
    operation: Dict[str, Any]
    timeout_ms: Optional[int] = None
    metadata: Dict[str, str] = field(default_factory=dict)


@dataclass
class WriteResponseMessage(Message):
    """Write response message from Proposer to Client."""
    request_id: str
    success: bool
    sequence_number: Optional[int] = None
    leader_hint: Optional[str] = None


@dataclass
class ReadRequestMessage(Message):
    """Read request message from Client."""
    request_id: str
    query: Dict[str, Any]
    consistency_level: str  # "strong", "session", "eventual"
    client_id: str


@dataclass
class ReadResponseMessage(Message):
    """Read response message to Client."""
    request_id: str
    result: Any
    sequence_number: int
    timestamp: float


@dataclass
class RedirectMessage(Message):
    """Redirect message to Client."""
    request_id: str
    correct_leader: str
    reason: str


@dataclass
class StatusRequestMessage(Message):
    """Status request message from Client."""
    request_id: str
    query_type: str
    client_id: str


@dataclass
class StatusResponseMessage(Message):
    """Status response message to Client."""
    request_id: str
    status_info: Dict[str, Any]
    topology_update: Optional[Dict[str, Any]] = None
