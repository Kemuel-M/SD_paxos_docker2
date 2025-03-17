"""
Proposer component implementation for Paxos protocol.
"""

import os
import time
import json
import uuid
import random
import threading
from typing import Dict, Any, List, Optional, Tuple
from collections import deque

import requests

from common.constants import (
    FOLLOWER, CANDIDATE, LEADER,
    PREPARE, ACCEPT, HEARTBEAT,
    PROMISE, NOT_PROMISE, ACCEPTED, NOT_ACCEPTED,
    WRITE_REQUEST, STATUS_REQUEST
)
from common.message import (
    PrepareMessage, AcceptMessage, HeartbeatMessage,
    WriteResponseMessage, RedirectMessage, StatusResponseMessage
)
from common.utils import setup_logger, parse_hosts, calculate_backoff


class Proposer:
    """Proposer implementation for Paxos protocol."""
    
    def __init__(self, proposer_id: str, acceptor_hosts: List[Tuple[str, int]], 
                 learner_hosts: List[Tuple[str, int]], heartbeat_interval: int = 500,
                 leader_timeout: int = 1500):
        """Initialize Proposer instance."""
        self.proposer_id = proposer_id
        self.acceptor_hosts = acceptor_hosts
        self.learner_hosts = learner_hosts
        self.heartbeat_interval = heartbeat_interval / 1000.0  # Convert to seconds
        self.leader_timeout = leader_timeout / 1000.0  # Convert to seconds
        
        self.logger = setup_logger(f"proposer-{proposer_id}")
        
        # State variables
        self.state = FOLLOWER
        self.counter = 0  # Local counter for proposal numbers
        self.leader_id = None
        self.last_heartbeat = 0
        self.heartbeat_sequence = 0
        
        # For Multi-Paxos optimization
        self.is_preparing = False
        self.prepare_quorum_achieved = False
        
        # Proposal queue and tracking
        self.proposal_queue = deque()
        self.active_proposals = {}  # proposal_number -> {'value': v, 'promises': [], 'accepts': []}
        
        # Start background threads
        self.stop_threads = False
        self.heartbeat_thread = threading.Thread(target=self._heartbeat_loop)
        self.election_thread = threading.Thread(target=self._election_monitor)
        self.proposal_thread = threading.Thread(target=self._proposal_processor)
        
        self.heartbeat_thread.daemon = True
        self.election_thread.daemon = True
        self.proposal_thread.daemon = True
        
        self.heartbeat_thread.start()
        self.election_thread.start()
        self.proposal_thread.start()
        
        self.logger.info(f"Proposer {proposer_id} initialized")
    
    def stop(self):
        """Stop the proposer background threads."""
        self.stop_threads = True
        self.heartbeat_thread.join(timeout=2)
        self.election_thread.join(timeout=2)
        self.proposal_thread.join(timeout=2)
        self.logger.info("Proposer stopped")
    
    def _generate_proposal_number(self) -> int:
        """Generate a unique proposal number."""
        self.counter += 1
        # Format: counter * 100 + ID to ensure uniqueness across proposers
        return (self.counter * 100) + int(self.proposer_id)
    
    def _calculate_quorum_size(self) -> int:
        """Calculate the quorum size based on the number of acceptors."""
        return (len(self.acceptor_hosts) // 2) + 1
    
    def _heartbeat_loop(self):
        """Loop to send heartbeats when leader."""
        while not self.stop_threads:
            try:
                if self.state == LEADER:
                    self._send_heartbeat()
                time.sleep(self.heartbeat_interval)
            except Exception as e:
                self.logger.error(f"Error in heartbeat loop: {e}")
    
    def _election_monitor(self):
        """Monitor for leader failures and initiate elections."""
        while not self.stop_threads:
            try:
                current_time = time.time()
                
                # If we're not the leader and haven't heard from a leader
                if (self.state != LEADER and 
                    (current_time - self.last_heartbeat) > self.leader_timeout and
                    not self.is_preparing):
                    
                    self.logger.info(f"Leader timeout detected. Last heartbeat: "
                                    f"{current_time - self.last_heartbeat:.2f}s ago")
                    
                    # Add some jitter to avoid all proposers starting election simultaneously
                    jitter = random.uniform(0, 1.0)
                    time.sleep(jitter)
                    
                    self._start_election()
                
                time.sleep(0.1)  # Check frequently but not constantly
            except Exception as e:
                self.logger.error(f"Error in election monitor: {e}")
                time.sleep(1)  # Back off on error
    
    def _proposal_processor(self):
        """Process queued proposals."""
        while not self.stop_threads:
            try:
                if self.state == LEADER and self.proposal_queue and self.prepare_quorum_achieved:
                    client_request = self.proposal_queue.popleft()
                    self._handle_client_proposal(client_request)
                time.sleep(0.05)  # Check frequently
            except Exception as e:
                self.logger.error(f"Error in proposal processor: {e}")
                time.sleep(1)  # Back off on error
    
    def _send_heartbeat(self):
        """Send heartbeat to all nodes."""
        self.heartbeat_sequence += 1
        heartbeat_msg = HeartbeatMessage(
            type=HEARTBEAT,
            leader_id=self.proposer_id,
            sequence_number=self.heartbeat_sequence,
            timestamp=time.time()
        )
        
        heartbeat_data = heartbeat_msg.to_dict()
        
        for host, port in self.acceptor_hosts:
            try:
                url = f"http://{host}:{port}/heartbeat"
                requests.post(url, json=heartbeat_data, timeout=2)
            except Exception as e:
                self.logger.warning(f"Failed to send heartbeat to acceptor {host}:{port}: {e}")
        
        # Also inform other proposers
        # This would need to be implemented with proposer-to-proposer communication
    
    def _start_election(self):
        """Start the election process."""
        if self.is_preparing:
            self.logger.debug("Already in an election, skipping")
            return
        
        self.is_preparing = True
        self.state = CANDIDATE
        proposal_number = self._generate_proposal_number()
        
        self.logger.info(f"Starting election with proposal number {proposal_number}")
        
        # Send prepare messages to all acceptors
        prepare_msg = PrepareMessage(
            type=PREPARE,
            proposal_number=proposal_number,
            proposer_id=self.proposer_id
        )
        
        # Initialize proposal tracking
        self.active_proposals[proposal_number] = {
            'value': None,  # Election doesn't have a value
            'promises': [],
            'accepted_value': None,
            'highest_accepted': 0
        }
        
        # Send prepare to all acceptors
        for host, port in self.acceptor_hosts:
            try:
                url = f"http://{host}:{port}/prepare"
                self.logger.debug(f"Sending PREPARE({proposal_number}) to {host}:{port}")
                
                response = requests.post(url, json=prepare_msg.to_dict(), timeout=5)
                response_data = response.json()
                
                self._handle_prepare_response(proposal_number, response_data)
            except Exception as e:
                self.logger.warning(f"Failed to send prepare to acceptor {host}:{port}: {e}")
        
        # Schedule cleanup of the election if it doesn't complete
        threading.Timer(
            10.0, 
            lambda: self._cleanup_election(proposal_number)
        ).start()
    
    def _cleanup_election(self, proposal_number: int):
        """Clean up an election if it doesn't complete."""
        if self.is_preparing and proposal_number in self.active_proposals:
            self.logger.info(f"Election with proposal {proposal_number} timed out")
            self.is_preparing = False
            self.active_proposals.pop(proposal_number, None)
    
    def _handle_prepare_response(self, proposal_number: int, response: Dict[str, Any]):
        """Handle response to a prepare message."""
        if proposal_number not in self.active_proposals:
            self.logger.warning(f"Received response for unknown proposal {proposal_number}")
            return
        
        proposal_data = self.active_proposals[proposal_number]
        
        if response['type'] == PROMISE:
            # Record the promise
            proposal_data['promises'].append(response)
            
            # Check if this promise contains an accepted value
            accepted_proposal = response.get('accepted_proposal')
            if accepted_proposal and accepted_proposal > proposal_data['highest_accepted']:
                proposal_data['highest_accepted'] = accepted_proposal
                proposal_data['accepted_value'] = response.get('accepted_value')
            
            # Check if we have a quorum of promises
            quorum_size = self._calculate_quorum_size()
            if len(proposal_data['promises']) >= quorum_size:
                self.logger.info(f"Achieved quorum of promises for proposal {proposal_number}")
                
                if self.state == CANDIDATE:
                    # Become leader
                    self._become_leader(proposal_number)
                else:
                    # For regular proposals (not elections), proceed to accept phase
                    self.prepare_quorum_achieved = True
                    if proposal_data['accepted_value'] is not None:
                        # Must use the highest accepted value from promises
                        self._send_accept(proposal_number, proposal_data['accepted_value'])
                    else:
                        # Can use our own value
                        self._send_accept(proposal_number, proposal_data['value'])
        
        elif response['type'] == NOT_PROMISE:
            self.logger.info(f"Received NOT_PROMISE for proposal {proposal_number}, "
                           f"promised to {response.get('promised_proposal')}")
            
            # If this is an election and we lose, update our leader
            if self.state == CANDIDATE:
                # Could potentially ask who the acceptor is promised to
                self.is_preparing = False
    
    def _become_leader(self, proposal_number: int):
        """Transition to leader state after winning election."""
        self.state = LEADER
        self.leader_id = self.proposer_id
        self.prepare_quorum_achieved = True
        self.is_preparing = False
        
        self.logger.info(f"Proposer {self.proposer_id} became leader with proposal {proposal_number}")
        
        # Send immediate heartbeat to announce leadership
        self._send_heartbeat()
    
    def _send_accept(self, proposal_number: int, value: Any):
        """Send accept messages to all acceptors."""
        if proposal_number not in self.active_proposals:
            self.logger.warning(f"Trying to send accept for unknown proposal {proposal_number}")
            return
        
        accept_msg = AcceptMessage(
            type=ACCEPT,
            proposal_number=proposal_number,
            value=value,
            proposer_id=self.proposer_id
        )
        
        proposal_data = self.active_proposals[proposal_number]
        proposal_data['accepts'] = []
        
        for host, port in self.acceptor_hosts:
            try:
                url = f"http://{host}:{port}/accept"
                self.logger.debug(f"Sending ACCEPT({proposal_number}, {value}) to {host}:{port}")
                
                response = requests.post(url, json=accept_msg.to_dict(), timeout=5)
                response_data = response.json()
                
                self._handle_accept_response(proposal_number, response_data)
            except Exception as e:
                self.logger.warning(f"Failed to send accept to acceptor {host}:{port}: {e}")
    
    def _handle_accept_response(self, proposal_number: int, response: Dict[str, Any]):
        """Handle response to an accept message."""
        if proposal_number not in self.active_proposals:
            self.logger.warning(f"Received accept response for unknown proposal {proposal_number}")
            return
        
        proposal_data = self.active_proposals[proposal_number]
        
        if response['type'] == ACCEPTED:
            # Record the acceptance
            proposal_data['accepts'].append(response)
            
            # Check if we have a quorum of acceptances
            quorum_size = self._calculate_quorum_size()
            if len(proposal_data['accepts']) >= quorum_size:
                self.logger.info(f"Achieved quorum of acceptances for proposal {proposal_number}")
                
                # Notify client if this was a client request
                self._notify_client_success(proposal_number)
                
                # Cleanup proposal data
                self.active_proposals.pop(proposal_number, None)
        
        elif response['type'] == NOT_ACCEPTED:
            self.logger.info(f"Received NOT_ACCEPTED for proposal {proposal_number}, "
                           f"promised to {response.get('promised_proposal')}")
            
            # If we're the leader and get NOT_ACCEPTED, might need to re-prepare
            if self.state == LEADER:
                promised_proposal = response.get('promised_proposal')
                if promised_proposal and promised_proposal > proposal_number:
                    self.logger.warning(f"Another proposer seems to be active with "
                                      f"higher proposal {promised_proposal}")
                    
                    # Back off and re-prepare with higher number
                    time.sleep(random.uniform(0.1, 0.5))
                    if self.state == LEADER:  # Still leader after sleep
                        self._retry_proposal(proposal_number, proposal_data['value'])
    
    def _retry_proposal(self, old_proposal_number: int, value: Any):
        """Retry a proposal that was rejected with a higher proposal number."""
        # Clean up old proposal
        self.active_proposals.pop(old_proposal_number, None)
        
        # Generate new proposal number
        new_proposal_number = self._generate_proposal_number()
        
        self.logger.info(f"Retrying proposal with number {new_proposal_number}, value: {value}")
        
        # Create new proposal tracking
        self.active_proposals[new_proposal_number] = {
            'value': value,
            'promises': [],
            'accepted_value': None,
            'highest_accepted': 0
        }
        
        # Send prepare messages for the new proposal
        prepare_msg = PrepareMessage(
            type=PREPARE,
            proposal_number=new_proposal_number,
            proposer_id=self.proposer_id
        )
        
        for host, port in self.acceptor_hosts:
            try:
                url = f"http://{host}:{port}/prepare"
                response = requests.post(url, json=prepare_msg.to_dict(), timeout=5)
                response_data = response.json()
                
                self._handle_prepare_response(new_proposal_number, response_data)
            except Exception as e:
                self.logger.warning(f"Failed to send prepare for retry to {host}:{port}: {e}")
    
    def _notify_client_success(self, proposal_number: int):
        """Notify client of successful proposal."""
        if proposal_number not in self.active_proposals:
            return
        
        proposal_data = self.active_proposals[proposal_number]
        client_request = proposal_data.get('client_request')
        
        if client_request:
            request_id = client_request.get('request_id')
            client_id = client_request.get('client_id')
            
            self.logger.info(f"Notifying client {client_id} of successful proposal {proposal_number}")
            
            # In a real implementation, this would send a response to the client
            # For now, we just log it
            self.logger.info(f"Proposal {proposal_number} for request {request_id} succeeded")
    
    def handle_client_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle a request from a client."""
        request_type = request.get('type')
        
        if self.state != LEADER:
            # Redirect to leader if known
            if self.leader_id:
                redirect_msg = RedirectMessage(
                    type="REDIRECT",
                    request_id=request.get('request_id'),
                    correct_leader=self.leader_id,
                    reason="not_leader"
                )
                return redirect_msg.to_dict()
            else:
                # No known leader, reject
                return {
                    "type": "ERROR",
                    "request_id": request.get('request_id'),
                    "error": "No known leader, try again later"
                }
        
        if request_type == WRITE_REQUEST:
            self.logger.info(f"Received write request: {request.get('request_id')}")
            
            # Queue the request for processing
            self.proposal_queue.append(request)
            
            # Return acknowledgment
            return {
                "type": "WRITE_ACKNOWLEDGMENT",
                "request_id": request.get('request_id'),
                "status": "queued",
                "leader_id": self.proposer_id
            }
        
        elif request_type == STATUS_REQUEST:
            # Handle status requests
            status_info = {
                "proposer_id": self.proposer_id,
                "state": self.state,
                "leader_id": self.leader_id,
                "queue_size": len(self.proposal_queue),
                "active_proposals": len(self.active_proposals)
            }
            
            status_msg = StatusResponseMessage(
                type="STATUS_RESPONSE",
                request_id=request.get('request_id'),
                status_info=status_info
            )
            
            return status_msg.to_dict()
        
        else:
            # Unknown request type
            return {
                "type": "ERROR",
                "request_id": request.get('request_id'),
                "error": f"Unknown request type: {request_type}"
            }
    
    def _handle_client_proposal(self, client_request: Dict[str, Any]):
        """Process a client proposal from the queue."""
        if self.state != LEADER:
            self.logger.warning("Not leader anymore, dropping client proposal")
            return
        
        # Generate proposal number
        proposal_number = self._generate_proposal_number()
        
        # Extract client data
        request_id = client_request.get('request_id')
        client_id = client_request.get('client_id')
        operation = client_request.get('operation')
        
        self.logger.info(f"Processing client request {request_id} from {client_id}")
        
        # Create proposal tracking
        self.active_proposals[proposal_number] = {
            'value': operation,
            'promises': [],
            'accepts': [],
            'client_request': client_request,
            'highest_accepted': 0,
            'accepted_value': None
        }
        
        # In Multi-Paxos, we skip the prepare phase after becoming leader
        if self.prepare_quorum_achieved:
            # Directly send accept
            self._send_accept(proposal_number, operation)
        else:
            # Need to do prepare phase first
            prepare_msg = PrepareMessage(
                type=PREPARE,
                proposal_number=proposal_number,
                proposer_id=self.proposer_id
            )
            
            for host, port in self.acceptor_hosts:
                try:
                    url = f"http://{host}:{port}/prepare"
                    response = requests.post(url, json=prepare_msg.to_dict(), timeout=5)
                    response_data = response.json()
                    
                    self._handle_prepare_response(proposal_number, response_data)
                except Exception as e:
                    self.logger.warning(f"Failed to send prepare to {host}:{port}: {e}")
