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
class PrepareMessage:
    """Prepare message from Proposer to Acceptor."""
    type: str
    proposal_number: int
    proposer_id: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class AcceptMessage:
    """Accept message from Proposer to Acceptor."""
    type: str
    proposal_number: int
    value: Any
    proposer_id: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class HeartbeatMessage:
    """Heartbeat message from Leader to all nodes."""
    type: str
    leader_id: str
    sequence_number: int
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class PromiseMessage:
    """Promise message from Acceptor to Proposer."""
    type: str
    proposal_number: int
    accepted_proposal: Optional[int] = None
    accepted_value: Optional[Any] = None
    tid: str = field(default_factory=generate_tid)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class NotPromiseMessage:
    """Not Promise message from Acceptor to Proposer."""
    type: str
    promised_proposal: int
    tid: str = field(default_factory=generate_tid)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class AcceptedMessage:
    """Accepted message from Acceptor to Proposer."""
    type: str
    proposal_number: int
    value: Any
    tid: str = field(default_factory=generate_tid)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class NotAcceptedMessage:
    """Not Accepted message from Acceptor to Proposer."""
    type: str
    promised_proposal: int
    tid: str = field(default_factory=generate_tid)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class LearnMessage:
    """Learn message from Acceptor to Learner."""
    type: str
    proposal_number: int
    value: Any
    acceptor_id: str
    tid: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class SyncRequestMessage:
    """Sync request message between Learners."""
    type: str
    from_seq: int
    to_seq: int
    learner_id: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class SyncResponseMessage:
    """Sync response message between Learners."""
    type: str
    decisions: List[Dict[str, Any]]
    learner_id: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class WriteRequestMessage:
    """Write request message from Client to Proposer."""
    type: str
    request_id: str
    client_id: str
    operation: Dict[str, Any]
    timeout_ms: Optional[int] = None
    metadata: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class WriteResponseMessage:
    """Write response message from Proposer to Client."""
    type: str
    request_id: str
    success: bool
    sequence_number: Optional[int] = None
    leader_hint: Optional[str] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class ReadRequestMessage:
    """Read request message from Client."""
    type: str
    request_id: str
    query: Dict[str, Any]
    consistency_level: str  # "strong", "session", "eventual"
    client_id: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class ReadResponseMessage:
    """Read response message to Client."""
    type: str
    request_id: str
    result: Any
    sequence_number: int
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class RedirectMessage:
    """Redirect message to Client."""
    type: str
    request_id: str
    correct_leader: str
    reason: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class StatusRequestMessage:
    """Status request message from Client."""
    type: str
    request_id: str
    query_type: str
    client_id: str
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)


@dataclass
class StatusResponseMessage:
    """Status response message to Client."""
    type: str
    request_id: str
    status_info: Dict[str, Any]
    topology_update: Optional[Dict[str, Any]] = None
    timestamp: float = field(default_factory=time.time)
    
    def to_dict(self):
        """Convert message to dictionary."""
        return asdict(self)