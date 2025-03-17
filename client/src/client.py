"""
Client component implementation for Paxos protocol.
"""

import os
import time
import json
import uuid
import random
import threading
from typing import Dict, Any, List, Optional, Tuple
from collections import defaultdict

import requests

from common.constants import (
    WRITE_REQUEST, READ_REQUEST, STATUS_REQUEST,
    WRITE_RESPONSE, READ_RESPONSE, STATUS_RESPONSE, REDIRECT,
    SUBSCRIBE, UNSUBSCRIBE
)
from common.message import (
    WriteRequestMessage, ReadRequestMessage, StatusRequestMessage
)
from common.utils import setup_logger, parse_hosts, generate_request_id, calculate_backoff


class PaxosClient:
    """Client implementation for interacting with Paxos cluster."""
    
    def __init__(self, client_id: str, proposer_hosts: List[Tuple[str, int]],
                learner_hosts: List[Tuple[str, int]]):
        """Initialize Client instance."""
        self.client_id = client_id
        self.proposer_hosts = proposer_hosts
        self.learner_hosts = learner_hosts
        
        self.logger = setup_logger(f"client-{client_id}")
        
        # Track known nodes and leader
        self.known_nodes = {}  # node_id -> NodeInfo
        self.current_leader = None
        
        # Track pending requests
        self.pending_requests = {}  # request_id -> RequestMetadata
        self.response_cache = {}  # request_id -> response
        self.retry_queue = []
        
        # Track highest seen sequence
        self.highest_seen_sequence = 0
        
        # Active sessions
        self.sessions = {}  # session_id -> SessionInfo
        
        # Background thread for retries
        self.stop_threads = False
        self.retry_thread = threading.Thread(target=self._process_retries)
        self.retry_thread.daemon = True
        self.retry_thread.start()
        
        # Discover the current leader
        self._discover_leader()
        
        self.logger.info(f"Client {client_id} initialized")
    
    def stop(self):
        """Stop the client background threads."""
        self.stop_threads = True
        self.retry_thread.join(timeout=2)
        self.logger.info("Client stopped")
    
    def _discover_leader(self) -> None:
        """Discover the current leader by querying proposers."""
        for host, port in self.proposer_hosts:
            try:
                url = f"http://{host}:{port}/status"
                response = requests.get(url, timeout=3)
                
                if response.status_code == 200:
                    status_data = response.json()
                    
                    # Update node info
                    node_id = status_data.get('proposer_id')
                    self.known_nodes[node_id] = {
                        'node_id': node_id,
                        'roles': ['proposer'],
                        'address': f"{host}:{port}",
                        'last_success': time.time(),
                        'failure_count': 0
                    }
                    
                    # Check if this is the leader
                    is_leader = status_data.get('state') == 'LEADER'
                    if is_leader:
                        self.current_leader = node_id
                        self.logger.info(f"Discovered leader: {node_id} at {host}:{port}")
                        return
                    
                    # If not leader, check if it knows the leader
                    leader_id = status_data.get('leader_id')
                    if leader_id:
                        self.current_leader = leader_id
                        self.logger.info(f"Discovered leader: {leader_id} (reported by {node_id})")
                        return
            except Exception as e:
                self.logger.warning(f"Failed to query proposer at {host}:{port}: {e}")
        
        self.logger.warning("Could not discover a leader")
    
    def _get_leader_address(self) -> Optional[Tuple[str, int]]:
        """Get the address of the current leader."""
        if not self.current_leader:
            return None
        
        leader_info = self.known_nodes.get(self.current_leader)
        if not leader_info:
            return None
        
        address = leader_info['address']
        host, port_str = address.split(':')
        return (host, int(port_str))
    
    def _get_random_proposer(self) -> Tuple[str, int]:
        """Get a random proposer address."""
        return random.choice(self.proposer_hosts)
    
    def _get_random_learner(self) -> Tuple[str, int]:
        """Get a random learner address."""
        return random.choice(self.learner_hosts)
    
    def _track_request(self, request_id: str, operation: Dict[str, Any], 
                      target_node: Tuple[str, int]) -> None:
        """Track a pending request."""
        self.pending_requests[request_id] = {
            'request_id': request_id,
            'operation': operation,
            'initial_timestamp': time.time(),
            'attempt_count': 1,
            'next_retry_time': time.time() + 5,  # First retry after 5 seconds
            'target_node': target_node
        }
    
    def _process_retries(self) -> None:
        """Process retry queue in the background."""
        while not self.stop_threads:
            try:
                current_time = time.time()
                
                # Check pending requests for timeouts
                for request_id, metadata in list(self.pending_requests.items()):
                    if current_time >= metadata['next_retry_time']:
                        self.logger.info(f"Request {request_id} timed out, queueing for retry")
                        self.retry_queue.append(request_id)
                        
                        # Update next retry time with exponential backoff
                        metadata['attempt_count'] += 1
                        backoff = calculate_backoff(metadata['attempt_count'])
                        metadata['next_retry_time'] = current_time + backoff
                
                # Process retry queue
                if self.retry_queue:
                    request_id = self.retry_queue.pop(0)
                    if request_id in self.pending_requests:
                        metadata = self.pending_requests[request_id]
                        operation = metadata['operation']
                        
                        self.logger.info(f"Retrying request {request_id}, attempt {metadata['attempt_count']}")
                        
                        # Rediscover leader first
                        self._discover_leader()
                        
                        # Retry based on operation type
                        if operation.get('message_type') == WRITE_REQUEST:
                            self._send_write_request(operation['value'], request_id)
                        elif operation.get('message_type') == READ_REQUEST:
                            self._send_read_request(operation['query'], operation['consistency'], request_id)
                        elif operation.get('message_type') == STATUS_REQUEST:
                            self._send_status_request(request_id)
                        
                        # If too many retries, give up
                        if metadata['attempt_count'] >= 5:
                            self.logger.warning(f"Giving up on request {request_id} after 5 attempts")
                            self.pending_requests.pop(request_id, None)
                
                time.sleep(0.1)  # Check frequently but not constantly
            except Exception as e:
                self.logger.error(f"Error in retry processor: {e}")
                time.sleep(1)  # Back off on error
    
    def _handle_redirect(self, response: Dict[str, Any]) -> None:
        """Handle redirect response."""
        correct_leader = response.get('correct_leader')
        if correct_leader:
            self.current_leader = correct_leader
            self.logger.info(f"Updated leader to {correct_leader}")
    
    def write(self, key: str, value: Any) -> Dict[str, Any]:
        """Write a key-value pair to the system."""
        operation = {
            'type': 'put',
            'key': key,
            'value': value
        }
        
        request_id = generate_request_id(self.client_id, operation)
        
        # Track the request before sending
        operation_metadata = {
            'message_type': WRITE_REQUEST,
            'value': operation
        }
        
        return self._send_write_request(operation, request_id, operation_metadata)
    
    def _send_write_request(self, operation: Dict[str, Any], request_id: str,
                          operation_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a write request to a proposer."""
        if not operation_metadata:
            operation_metadata = {
                'message_type': WRITE_REQUEST,
                'value': operation
            }
        
        # Prepare write request message
        write_request = WriteRequestMessage(
            type=WRITE_REQUEST,
            request_id=request_id,
            client_id=self.client_id,
            operation=operation
        )
        
        # Try to send to current leader first
        leader_address = self._get_leader_address()
        if leader_address:
            host, port = leader_address
        else:
            # Fall back to random proposer
            host, port = self._get_random_proposer()
        
        target = (host, port)
        
        try:
            url = f"http://{host}:{port}/request"
            self.logger.info(f"Sending write request {request_id} to {host}:{port}")
            
            # Track the request
            if operation_metadata:
                self._track_request(request_id, operation_metadata, target)
            
            # Send the request
            response = requests.post(url, json=write_request.to_dict(), timeout=5)
            response_data = response.json()
            
            # Handle response
            if response_data.get('type') == 'WRITE_ACKNOWLEDGMENT':
                self.logger.info(f"Write request {request_id} acknowledged by {host}:{port}")
                return response_data
            elif response_data.get('type') == REDIRECT:
                self._handle_redirect(response_data)
                # Retry with new leader will happen via retry mechanism
                return response_data
            else:
                self.logger.warning(f"Unexpected response type: {response_data.get('type')}")
                return response_data
            
        except Exception as e:
            self.logger.error(f"Error sending write request to {host}:{port}: {e}")
            return {"error": str(e), "status": "failed", "request_id": request_id}
    
    def read(self, key: str, consistency: str = "eventual") -> Dict[str, Any]:
        """Read a value by key from the system."""
        query = {
            'key': key
        }
        
        request_id = generate_request_id(self.client_id, query)
        
        # Track the request before sending
        operation_metadata = {
            'message_type': READ_REQUEST,
            'query': query,
            'consistency': consistency
        }
        
        return self._send_read_request(query, consistency, request_id, operation_metadata)
    
    def _send_read_request(self, query: Dict[str, Any], consistency: str, request_id: str,
                         operation_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a read request to a learner or proposer based on consistency level."""
        if not operation_metadata:
            operation_metadata = {
                'message_type': READ_REQUEST,
                'query': query,
                'consistency': consistency
            }
        
        # Prepare read request message
        read_request = ReadRequestMessage(
            type=READ_REQUEST,
            request_id=request_id,
            query=query,
            consistency_level=consistency,
            client_id=self.client_id
        )
        
        # Choose target based on consistency level
        if consistency == "strong":
            # Strong consistency needs to go through leader
            leader_address = self._get_leader_address()
            if leader_address:
                host, port = leader_address
                url = f"http://{host}:{port}/request"
            else:
                # Fall back to random proposer
                host, port = self._get_random_proposer()
                url = f"http://{host}:{port}/request"
        else:
            # Eventual or session consistency can go directly to learner
            host, port = self._get_random_learner()
            url = f"http://{host}:{port}/read"
        
        target = (host, port)
        
        try:
            self.logger.info(f"Sending read request {request_id} to {host}:{port}, consistency={consistency}")
            
            # Track the request
            if operation_metadata:
                self._track_request(request_id, operation_metadata, target)
            
            # Send the request
            response = requests.post(url, json=read_request.to_dict(), timeout=5)
            response_data = response.json()
            
            # Handle response
            if response_data.get('type') == 'READ_RESPONSE':
                self.logger.info(f"Read request {request_id} completed")
                
                # Update highest seen sequence if this was a real result
                sequence_number = response_data.get('sequence_number')
                if sequence_number and sequence_number > self.highest_seen_sequence:
                    self.highest_seen_sequence = sequence_number
                
                # Remove from pending
                self.pending_requests.pop(request_id, None)
                
                return response_data
            elif response_data.get('type') == REDIRECT:
                self._handle_redirect(response_data)
                # Retry with new leader will happen via retry mechanism
                return response_data
            else:
                self.logger.warning(f"Unexpected response type: {response_data.get('type')}")
                return response_data
            
        except Exception as e:
            self.logger.error(f"Error sending read request to {host}:{port}: {e}")
            return {"error": str(e), "status": "failed", "request_id": request_id}
    
    def get_status(self) -> Dict[str, Any]:
        """Get status of the Paxos cluster."""
        request_id = generate_request_id(self.client_id, {"type": "status"})
        
        # Track the request before sending
        operation_metadata = {
            'message_type': STATUS_REQUEST,
            'query_type': 'cluster_status'
        }
        
        return self._send_status_request(request_id, operation_metadata)
    
    def _send_status_request(self, request_id: str,
                           operation_metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send a status request to a proposer."""
        if not operation_metadata:
            operation_metadata = {
                'message_type': STATUS_REQUEST,
                'query_type': 'cluster_status'
            }
        
        # Prepare status request message
        status_request = StatusRequestMessage(
            type=STATUS_REQUEST,
            request_id=request_id,
            query_type='cluster_status',
            client_id=self.client_id
        )
        
        # Try to send to current leader first
        leader_address = self._get_leader_address()
        if leader_address:
            host, port = leader_address
        else:
            # Fall back to random proposer
            host, port = self._get_random_proposer()
        
        target = (host, port)
        
        try:
            url = f"http://{host}:{port}/status"
            self.logger.info(f"Sending status request {request_id} to {host}:{port}")
            
            # Track the request
            if operation_metadata:
                self._track_request(request_id, operation_metadata, target)
            
            # Send the request (GET for status)
            response = requests.get(url, timeout=5)
            response_data = response.json()
            
            # Remove from pending
            self.pending_requests.pop(request_id, None)
            
            # Handle leader info
            if 'leader_id' in response_data:
                leader_id = response_data.get('leader_id')
                if leader_id and leader_id != 'unknown':
                    self.current_leader = leader_id
            
            return response_data
            
        except Exception as e:
            self.logger.error(f"Error sending status request to {host}:{port}: {e}")
            return {"error": str(e), "status": "failed", "request_id": request_id}
    
    def subscribe(self, patterns: List[str]) -> Dict[str, Any]:
        """Subscribe to notifications based on patterns."""
        request_id = generate_request_id(self.client_id, {"type": "subscribe", "patterns": patterns})
        
        # Create subscription request
        subscribe_request = {
            "type": SUBSCRIBE,
            "client_id": self.client_id,
            "interest_patterns": patterns,
            "options": {
                "push": True,
                "expiry": time.time() + 3600  # 1 hour expiry
            }
        }
        
        # Choose a random learner for subscription
        host, port = self._get_random_learner()
        
        try:
            url = f"http://{host}:{port}/subscribe"
            self.logger.info(f"Sending subscription request to {host}:{port}")
            
            # Send the request
            response = requests.post(url, json=subscribe_request, timeout=5)
            response_data = response.json()
            
            if response_data.get('type') == 'SUBSCRIPTION_CONFIRMATION':
                self.logger.info(f"Subscription confirmed: {response_data.get('subscription_id')}")
            
            return response_data
            
        except Exception as e:
            self.logger.error(f"Error sending subscription request: {e}")
            return {"error": str(e), "status": "failed"}
    
    def unsubscribe(self, subscription_id: str) -> Dict[str, Any]:
        """Unsubscribe from notifications."""
        # Create unsubscribe request
        unsubscribe_request = {
            "type": UNSUBSCRIBE,
            "subscription_id": subscription_id,
            "client_id": self.client_id
        }
        
        # Choose a random learner for unsubscription
        host, port = self._get_random_learner()
        
        try:
            url = f"http://{host}:{port}/unsubscribe"
            self.logger.info(f"Sending unsubscription request for {subscription_id}")
            
            # Send the request
            response = requests.post(url, json=unsubscribe_request, timeout=5)
            response_data = response.json()
            
            return response_data
            
        except Exception as e:
            self.logger.error(f"Error sending unsubscription request: {e}")
            return {"error": str(e), "status": "failed"}
