"""
Learner component implementation for Paxos protocol.
"""

import os
import time
import json
import uuid
import threading
from typing import Dict, Any, List, Optional, Tuple, Set

import requests

from common.constants import (
    LEARN, SYNC_REQUEST, SYNC_RESPONSE, SNAPSHOT_REQUEST, SNAPSHOT_RESPONSE,
    CONSISTENCY_CHECK, READ_REQUEST, SUBSCRIBE, UNSUBSCRIBE
)
from common.message import (
    LearnMessage, SyncRequestMessage, SyncResponseMessage,
    ReadResponseMessage, StatusResponseMessage
)
from common.utils import setup_logger, save_to_file, load_from_file, parse_hosts


class Learner:
    """Learner implementation for Paxos protocol."""
    
    def __init__(self, learner_id: str, data_dir: str = "/data", 
                 acceptor_hosts: List[Tuple[str, int]] = None,
                 learner_hosts: List[Tuple[str, int]] = None,
                 total_acceptors: int = 3, quorum_size: int = 2):
        """Initialize Learner instance."""
        self.learner_id = learner_id
        self.data_dir = f"{data_dir}/learner{learner_id}"
        self.state_file = f"{self.data_dir}/state.json"
        self.log_file = f"{self.data_dir}/decisions_log.json"
        self.snapshot_file = f"{self.data_dir}/state_snapshot.json"
        
        self.acceptor_hosts = acceptor_hosts or []
        self.other_learners = learner_hosts or []
        self.total_acceptors = total_acceptors
        self.quorum_size = quorum_size
        
        self.logger = setup_logger(f"learner-{learner_id}")
        
        # Initialize learner state
        self.decisions = {}  # proposal_number -> DecisionEntry
        self.last_applied = 0
        self.highest_seen = 0
        
        # Tracking acceptor confirmations
        self.acceptor_confirmations = {}  # proposal_number -> Set[acceptor_id]
        
        # Application state (would be determined by the actual application)
        self.application_state = {}
        
        # Subscriptions from clients
        self.subscriptions = {}  # subscription_id -> subscription_info
        
        # Load state if available
        self._load_state()
        
        # Start background synchronization
        self.stop_threads = False
        self.sync_thread = threading.Thread(target=self._periodic_sync)
        self.sync_thread.daemon = True
        self.sync_thread.start()
        
        self.logger.info(f"Learner {learner_id} initialized. Last applied: {self.last_applied}, "
                        f"highest seen: {self.highest_seen}")
    
    def stop(self):
        """Stop the learner background threads."""
        self.stop_threads = True
        self.sync_thread.join(timeout=2)
        self.logger.info("Learner stopped")
    
    def _load_state(self) -> None:
        """Load learner state from persistent storage."""
        # Load decisions log
        decisions_log = load_from_file(self.log_file)
        if decisions_log:
            self.decisions = decisions_log
            self.logger.info(f"Loaded {len(self.decisions)} decisions from log")
            
            # Determine highest seen and last applied
            proposal_numbers = [int(p) for p in self.decisions.keys()]
            if proposal_numbers:
                self.highest_seen = max(proposal_numbers)
                
                # Last applied is the highest consecutive proposal number
                sorted_proposals = sorted(proposal_numbers)
                for i, p in enumerate(sorted_proposals):
                    if i == 0 or p == sorted_proposals[i-1] + 1:
                        self.last_applied = p
                    else:
                        break
        
        # Load application state snapshot
        state_snapshot = load_from_file(self.snapshot_file)
        if state_snapshot:
            self.application_state = state_snapshot.get('state', {})
            snapshot_version = state_snapshot.get('version', 0)
            self.logger.info(f"Loaded application state snapshot version {snapshot_version}")
    
    def _save_decisions_log(self) -> None:
        """Save decisions log to persistent storage."""
        success = save_to_file(self.decisions, self.log_file)
        if not success:
            self.logger.error("Failed to save decisions log")
    
    def _save_state_snapshot(self) -> None:
        """Save application state snapshot to persistent storage."""
        snapshot = {
            'state': self.application_state,
            'version': self.last_applied,
            'timestamp': time.time()
        }
        success = save_to_file(snapshot, self.snapshot_file)
        if not success:
            self.logger.error("Failed to save application state snapshot")
    
    def _create_decision_entry(self, proposal_number: int, value: Any, 
                              acceptor_id: str) -> Dict[str, Any]:
        """Create a new decision entry."""
        return {
            'proposal_number': proposal_number,
            'value': value,
            'confirming_acceptors': [acceptor_id],
            'first_notification': time.time(),
            'last_notification': time.time(),
            'is_definitely_decided': False
        }
    
    def _update_decision_entry(self, proposal_number: int, acceptor_id: str) -> None:
        """Update an existing decision entry with a new acceptor confirmation."""
        if str(proposal_number) in self.decisions:
            entry = self.decisions[str(proposal_number)]
            if acceptor_id not in entry['confirming_acceptors']:
                entry['confirming_acceptors'].append(acceptor_id)
            entry['last_notification'] = time.time()
            
            # Check if quorum is reached
            if len(entry['confirming_acceptors']) >= self.quorum_size:
                entry['is_definitely_decided'] = True
                
                # Apply to application state if this is the next in sequence
                if (self.last_applied + 1) == proposal_number:
                    self._apply_decision(proposal_number)
    
    def _apply_decision(self, proposal_number: int) -> None:
        """Apply a decision to the application state."""
        if str(proposal_number) not in self.decisions:
            return
        
        entry = self.decisions[str(proposal_number)]
        value = entry['value']
        
        # In a real application, this would apply the value/operation to the state
        self.logger.info(f"Applying decision {proposal_number}: {value}")
        
        # For this example, we just store the value in our state
        if isinstance(value, dict) and 'operation' in value:
            operation = value['operation']
            if operation.get('type') == 'put':
                key = operation.get('key')
                val = operation.get('value')
                self.application_state[key] = val
                self.logger.info(f"Updated state: {key} = {val}")
            elif operation.get('type') == 'delete':
                key = operation.get('key')
                if key in self.application_state:
                    del self.application_state[key]
                    self.logger.info(f"Deleted key: {key}")
        
        # Update last applied
        self.last_applied = proposal_number
        
        # Save state snapshot periodically (e.g., every 10 decisions)
        if proposal_number % 10 == 0:
            self._save_state_snapshot()
        
        # Apply next decisions if they're available and in sequence
        next_proposal = proposal_number + 1
        while str(next_proposal) in self.decisions and self.decisions[str(next_proposal)]['is_definitely_decided']:
            self._apply_decision(next_proposal)
            next_proposal += 1
    
    def handle_learn(self, learn_msg: Dict[str, Any]) -> Dict[str, Any]:
        """Handle learn message from acceptor."""
        proposal_number = learn_msg['proposal_number']
        value = learn_msg['value']
        acceptor_id = learn_msg['acceptor_id']
        tid = learn_msg['tid']
        
        self.logger.info(f"Received LEARN({proposal_number}) from acceptor {acceptor_id}")
        
        # Update highest seen proposal
        if proposal_number > self.highest_seen:
            self.highest_seen = proposal_number
        
        # Check if we already know about this proposal
        if str(proposal_number) in self.decisions:
            # Update existing entry
            self._update_decision_entry(proposal_number, acceptor_id)
        else:
            # Create new entry
            self.decisions[str(proposal_number)] = self._create_decision_entry(
                proposal_number, value, acceptor_id
            )
        
        # Save decisions log
        self._save_decisions_log()
        
        # Check for gaps in sequence
        self._check_for_gaps()
        
        # Notify subscribed clients
        self._notify_subscribed_clients(proposal_number, value)
        
        # Return acknowledgment
        return {
            "type": "LEARN_ACK",
            "learner_id": self.learner_id,
            "proposal_number": proposal_number,
            "timestamp": time.time()
        }
    
    def _check_for_gaps(self) -> None:
        """Check for gaps in the decision sequence and try to fill them."""
        if not self.decisions:
            return
        
        # Find gaps between last_applied and highest_seen
        next_expected = self.last_applied + 1
        
        while next_expected <= self.highest_seen:
            if str(next_expected) not in self.decisions:
                self.logger.info(f"Detected gap at proposal {next_expected}, requesting sync")
                self._request_sync(next_expected, self.highest_seen)
                break
            next_expected += 1
    
    def _request_sync(self, from_seq: int, to_seq: int) -> None:
        """Request synchronization from other learners for missing decisions."""
        if not self.other_learners:
            return
        
        sync_request = SyncRequestMessage(
            type=SYNC_REQUEST,
            from_seq=from_seq,
            to_seq=to_seq,
            learner_id=self.learner_id
        )
        
        # Try to sync from other learners
        for host, port in self.other_learners:
            try:
                url = f"http://{host}:{port}/sync"
                response = requests.post(url, json=sync_request.to_dict(), timeout=5)
                
                if response.status_code == 200:
                    sync_response = response.json()
                    if sync_response['type'] == SYNC_RESPONSE:
                        self._handle_sync_response(sync_response)
                        break
            except Exception as e:
                self.logger.warning(f"Failed to request sync from learner at {host}:{port}: {e}")
    
    def _handle_sync_response(self, sync_response: Dict[str, Any]) -> None:
        """Handle synchronization response from another learner."""
        decisions = sync_response.get('decisions', [])
        learner_id = sync_response.get('learner_id')
        
        self.logger.info(f"Received sync response from learner {learner_id} "
                        f"with {len(decisions)} decisions")
        
        # Update our decisions with the synced ones
        for decision in decisions:
            proposal_number = decision['proposal_number']
            
            if str(proposal_number) not in self.decisions:
                self.decisions[str(proposal_number)] = decision
                
                # If this decision has a quorum and is the next one we need, apply it
                if (decision['is_definitely_decided'] and 
                    proposal_number == (self.last_applied + 1)):
                    self._apply_decision(proposal_number)
            
            if proposal_number > self.highest_seen:
                self.highest_seen = proposal_number
        
        # Save updated decisions log
        self._save_decisions_log()
        
        # Check if we still have gaps
        self._check_for_gaps()
    
    def handle_sync_request(self, sync_request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle synchronization request from another learner."""
        from_seq = sync_request['from_seq']
        to_seq = sync_request['to_seq']
        requester_id = sync_request['learner_id']
        
        self.logger.info(f"Received sync request from learner {requester_id} "
                        f"for proposals {from_seq} to {to_seq}")
        
        # Collect the requested decisions
        requested_decisions = []
        for seq in range(from_seq, to_seq + 1):
            if str(seq) in self.decisions:
                requested_decisions.append(self.decisions[str(seq)])
        
        # Create and return sync response
        sync_response = SyncResponseMessage(
            type=SYNC_RESPONSE,
            decisions=requested_decisions,
            learner_id=self.learner_id
        )
        
        return sync_response.to_dict()
    
    def handle_read_request(self, read_request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle read request from client."""
        request_id = read_request['request_id']
        query = read_request['query']
        consistency_level = read_request['consistency_level']
        client_id = read_request['client_id']
        
        self.logger.info(f"Received READ_REQUEST from client {client_id}, consistency={consistency_level}")
        
        # Determine result based on query type
        result = None
        
        if 'key' in query:
            key = query['key']
            result = self.application_state.get(key)
        elif query.get('type') == 'all':
            result = self.application_state.copy()
        elif query.get('type') == 'prefix':
            prefix = query.get('prefix', '')
            result = {k: v for k, v in self.application_state.items() if k.startswith(prefix)}
        
        # Create read response
        read_response = ReadResponseMessage(
            type="READ_RESPONSE",
            request_id=request_id,
            result=result,
            sequence_number=self.last_applied,
            timestamp=time.time()
        )
        
        return read_response.to_dict()
    
    def handle_subscribe(self, subscribe_request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle subscription request from client."""
        client_id = subscribe_request['client_id']
        interest_patterns = subscribe_request.get('interest_patterns', [])
        options = subscribe_request.get('options', {})
        
        subscription_id = str(uuid.uuid4())
        
        self.logger.info(f"Received SUBSCRIBE from client {client_id}, patterns={interest_patterns}")
        
        # Store subscription
        self.subscriptions[subscription_id] = {
            'subscription_id': subscription_id,
            'client_id': client_id,
            'interest_patterns': interest_patterns,
            'options': options,
            'created_at': time.time(),
            'last_notification': time.time()
        }
        
        # Return confirmation
        return {
            "type": "SUBSCRIPTION_CONFIRMATION",
            "subscription_id": subscription_id,
            "details": {
                "created_at": time.time(),
                "patterns": interest_patterns
            }
        }
    
    def handle_unsubscribe(self, unsubscribe_request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle unsubscribe request from client."""
        subscription_id = unsubscribe_request['subscription_id']
        client_id = unsubscribe_request['client_id']
        
        self.logger.info(f"Received UNSUBSCRIBE from client {client_id}, "
                        f"subscription={subscription_id}")
        
        # Remove subscription if exists
        if subscription_id in self.subscriptions:
            del self.subscriptions[subscription_id]
            status = "success"
        else:
            status = "not_found"
        
        # Return confirmation
        return {
            "type": "UNSUBSCRIBE_CONFIRMATION",
            "subscription_id": subscription_id,
            "status": status
        }
    
    def _notify_subscribed_clients(self, proposal_number: int, value: Any) -> None:
        """Notify subscribed clients about new decisions."""
        # In a real implementation, this would send notifications to subscribed clients
        # For this example, we just log the notification
        if not self.subscriptions:
            return
        
        self.logger.info(f"Would notify {len(self.subscriptions)} subscribed clients "
                        f"about proposal {proposal_number}")
        
        # Check which subscriptions match this value
        for sub_id, subscription in self.subscriptions.items():
            # Check if this value matches any interest patterns
            # For simplicity, we're not implementing actual pattern matching here
            
            # Update last notification time
            subscription['last_notification'] = time.time()
    
    def _periodic_sync(self) -> None:
        """Periodically synchronize with other learners and check for gaps."""
        while not self.stop_threads:
            try:
                # Check for gaps every 5 seconds
                self._check_for_gaps()
                
                # Perform consistency check with other learners occasionally
                if random.random() < 0.1:  # 10% chance each cycle
                    self._check_consistency_with_others()
                
                time.sleep(5)
            except Exception as e:
                self.logger.error(f"Error in periodic sync: {e}")
                time.sleep(5)  # Back off on error
    
    def _check_consistency_with_others(self) -> None:
        """Check consistency with other learners."""
        # This would send consistency check messages to other learners
        # and reconcile any differences
        # For simplicity, we're not implementing the full protocol here
        pass
    
    def get_status(self) -> Dict[str, Any]:
        """Get learner status information."""
        return {
            "learner_id": self.learner_id,
            "last_applied": self.last_applied,
            "highest_seen": self.highest_seen,
            "total_decisions": len(self.decisions),
            "state_size": len(self.application_state),
            "active_subscriptions": len(self.subscriptions),
            "quorum_size": self.quorum_size
        }
