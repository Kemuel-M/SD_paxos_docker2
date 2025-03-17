"""
Acceptor component implementation for Paxos protocol.
"""

import os
import time
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple

import requests

from common.constants import (
    PREPARE, ACCEPT, HEARTBEAT, 
    PROMISE, NOT_PROMISE, ACCEPTED, NOT_ACCEPTED, LEARN
)
from common.message import (
    PrepareMessage, AcceptMessage, HeartbeatMessage, 
    PromiseMessage, NotPromiseMessage, AcceptedMessage, NotAcceptedMessage, LearnMessage
)
from common.utils import setup_logger, save_to_file, load_from_file


class Acceptor:
    """Acceptor implementation for Paxos protocol."""
    
    def __init__(self, acceptor_id: str, data_dir: str = "/data", total_acceptors: int = 3):
        """Initialize Acceptor instance."""
        self.acceptor_id = acceptor_id
        self.data_dir = f"{data_dir}/acceptor{acceptor_id}"
        self.state_file = f"{self.data_dir}/state.json"
        self.logger = setup_logger(f"acceptor-{acceptor_id}")
        
        # Initialize state
        self.max_promised = 0
        self.max_accepted = 0
        self.accepted_value = None
        self.log_proposals = {}  # proposal_number -> ProposalRecord
        self.last_heartbeat_time = {}  # proposer_id -> timestamp
        self.current_leader_id = None
        
        # Load persistent state if available
        self._load_state()
        
        self.logger.info(f"Acceptor {acceptor_id} initialized with max_promised={self.max_promised}, "
                         f"max_accepted={self.max_accepted}")
    
    def _load_state(self) -> None:
        """Load acceptor state from persistent storage."""
        state = load_from_file(self.state_file)
        if state:
            self.max_promised = state.get('max_promised', 0)
            self.max_accepted = state.get('max_accepted', 0)
            self.accepted_value = state.get('accepted_value')
            self.log_proposals = state.get('log_proposals', {})
            self.logger.info(f"Loaded state from {self.state_file}")
    
    def _save_state(self) -> None:
        """Save acceptor state to persistent storage."""
        state = {
            'max_promised': self.max_promised,
            'max_accepted': self.max_accepted,
            'accepted_value': self.accepted_value,
            'log_proposals': self.log_proposals
        }
        success = save_to_file(state, self.state_file)
        if success:
            self.logger.debug(f"Saved state to {self.state_file}")
        else:
            self.logger.error(f"Failed to save state to {self.state_file}")
    
    def _create_proposal_record(self, proposal_number: int, tid: str) -> Dict[str, Any]:
        """Create a new proposal record."""
        return {
            'proposal_number': proposal_number,
            'tid': tid,
            'promise_time': time.time(),
            'was_accepted': False,
            'accept_time': None,
            'value': None
        }
    
    def _update_proposal_record(self, proposal_number: int, value: Any = None, 
                               was_accepted: bool = False) -> None:
        """Update an existing proposal record."""
        if str(proposal_number) in self.log_proposals:
            record = self.log_proposals[str(proposal_number)]
            if was_accepted:
                record['was_accepted'] = True
                record['accept_time'] = time.time()
                record['value'] = value
                self.log_proposals[str(proposal_number)] = record
    
    def handle_prepare(self, prepare_msg: PrepareMessage) -> Dict[str, Any]:
        """Handle prepare message from proposer."""
        proposal_number = prepare_msg.proposal_number
        proposer_id = prepare_msg.proposer_id
        
        self.logger.info(f"Received PREPARE({proposal_number}) from proposer {proposer_id}")
        
        # Record heartbeat time for this proposer
        self.last_heartbeat_time[proposer_id] = time.time()
        
        # Generate a unique transaction ID
        tid = str(uuid.uuid4())
        
        # Check if we can promise
        if proposal_number > self.max_promised:
            # Create proposal record
            self.log_proposals[str(proposal_number)] = self._create_proposal_record(
                proposal_number, tid
            )
            
            # Update max_promised
            old_max_promised = self.max_promised
            self.max_promised = proposal_number
            
            # Persist state before responding
            self._save_state()
            
            # Create promise response
            promise_msg = PromiseMessage(
                type=PROMISE,
                proposal_number=proposal_number,
                accepted_proposal=self.max_accepted if self.max_accepted > 0 else None,
                accepted_value=self.accepted_value,
                tid=tid
            )
            
            self.logger.info(f"Sending PROMISE for proposal {proposal_number} "
                            f"(old max_promised={old_max_promised})")
            return promise_msg.to_dict()
        else:
            # Cannot promise, send rejection
            not_promise_msg = NotPromiseMessage(
                type=NOT_PROMISE,
                promised_proposal=self.max_promised,
                tid=tid
            )
            
            self.logger.info(f"Sending NOT_PROMISE for proposal {proposal_number} "
                            f"(max_promised={self.max_promised})")
            return not_promise_msg.to_dict()
    
    def handle_accept(self, accept_msg: AcceptMessage) -> Dict[str, Any]:
        """Handle accept message from proposer."""
        proposal_number = accept_msg.proposal_number
        value = accept_msg.value
        proposer_id = accept_msg.proposer_id
        
        self.logger.info(f"Received ACCEPT({proposal_number}, {value}) from proposer {proposer_id}")
        
        # Record heartbeat time for this proposer
        self.last_heartbeat_time[proposer_id] = time.time()
        
        # Generate a unique transaction ID
        tid = str(uuid.uuid4())
        
        # Check if we can accept
        if proposal_number >= self.max_promised:
            # Update state
            self.max_promised = proposal_number
            self.max_accepted = proposal_number
            self.accepted_value = value
            
            # Update proposal record if exists
            self._update_proposal_record(proposal_number, value, True)
            
            # Persist state before responding
            self._save_state()
            
            # Create accepted response
            accepted_msg = AcceptedMessage(
                type=ACCEPTED,
                proposal_number=proposal_number,
                value=value,
                tid=tid
            )
            
            self.logger.info(f"Sending ACCEPTED for proposal {proposal_number}")
            
            # Notify learners about the accepted value
            self._notify_learners(proposal_number, value, tid)
            
            return accepted_msg.to_dict()
        else:
            # Cannot accept, send rejection
            not_accepted_msg = NotAcceptedMessage(
                type=NOT_ACCEPTED,
                promised_proposal=self.max_promised,
                tid=tid
            )
            
            self.logger.info(f"Sending NOT_ACCEPTED for proposal {proposal_number} "
                            f"(max_promised={self.max_promised})")
            return not_accepted_msg.to_dict()
    
    def handle_heartbeat(self, heartbeat_msg: HeartbeatMessage) -> Dict[str, Any]:
        """Handle heartbeat message from proposer."""
        leader_id = heartbeat_msg.leader_id
        sequence_number = heartbeat_msg.sequence_number
        
        self.logger.debug(f"Received HEARTBEAT from leader {leader_id} "
                         f"with sequence number {sequence_number}")
        
        # Update leader information
        self.current_leader_id = leader_id
        self.last_heartbeat_time[leader_id] = time.time()
        
        # Simple ACK response
        return {
            "type": "HEARTBEAT_ACK",
            "acceptor_id": self.acceptor_id,
            "timestamp": time.time()
        }
    
    def _notify_learners(self, proposal_number: int, value: Any, tid: str) -> None:
        """Notify learners about accepted value."""
        # In a real implementation, this would send notifications to the learners
        # For demonstration, we'll just log the notification
        self.logger.info(f"Would notify learners: LEARN({proposal_number}, {value})")
        
        # Actual implementation would use configuration to know learner endpoints
        # and send actual HTTP requests or use a message queue
        learn_msg = LearnMessage(
            type=LEARN,
            proposal_number=proposal_number,
            value=value,
            acceptor_id=self.acceptor_id,
            tid=tid
        )
        
        # Placeholder for actual notification logic
        # self._send_to_learners(learn_msg.to_dict())
    
    def _send_to_learners(self, message: Dict[str, Any]) -> None:
        """Send message to all learners."""
        # This would be implemented to send HTTP requests or use message queues
        # to send the message to all configured learners
        pass
