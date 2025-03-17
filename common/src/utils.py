"""
Utility functions for the Paxos implementation.
"""

import json
import logging
import os
import time
import hashlib
import random
from typing import Dict, List, Any, Tuple, Optional

# Configure logging
def setup_logger(name, log_level=None):
    """Set up logger with specified log level."""
    if log_level is None:
        log_level = os.environ.get('LOG_LEVEL', 'INFO')
    
    numeric_level = getattr(logging, log_level.upper(), None)
    if not isinstance(numeric_level, int):
        numeric_level = logging.INFO
    
    logger = logging.getLogger(name)
    logger.setLevel(numeric_level)
    
    # Create console handler if not already added
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger

# File persistence utilities
def save_to_file(data: Any, filepath: str) -> bool:
    """Save data to file."""
    try:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w') as f:
            json.dump(data, f)
        return True
    except Exception as e:
        logger = setup_logger('utils')
        logger.error(f"Error saving to file {filepath}: {e}")
        return False

def load_from_file(filepath: str) -> Optional[Any]:
    """Load data from file."""
    try:
        if not os.path.exists(filepath):
            return None
        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception as e:
        logger = setup_logger('utils')
        logger.error(f"Error loading from file {filepath}: {e}")
        return None

# Network utilities
def parse_hosts(hosts_str: str) -> List[Tuple[str, int]]:
    """Parse hosts string into list of (host, port) tuples."""
    if not hosts_str:
        return []
    
    hosts = []
    for host_str in hosts_str.split(','):
        host_parts = host_str.strip().split(':')
        if len(host_parts) == 2:
            host, port = host_parts
            hosts.append((host, int(port)))
    
    return hosts

# Unique ID generation
def generate_request_id(client_id: str, operation: Dict[str, Any]) -> str:
    """Generate a unique request ID for client operations."""
    timestamp = str(time.time())
    nonce = str(random.randint(0, 999999))
    data = f"{client_id}:{json.dumps(operation)}:{timestamp}:{nonce}"
    return hashlib.sha256(data.encode()).hexdigest()

# Exponential backoff
def calculate_backoff(attempt: int, base_ms: int = 100, max_ms: int = 10000) -> float:
    """Calculate exponential backoff time in seconds."""
    backoff_ms = min(base_ms * (2 ** attempt), max_ms)
    jitter = random.uniform(0.8, 1.2)  # Add jitter to avoid thundering herd
    return (backoff_ms * jitter) / 1000  # Convert to seconds
