"""
Constants for the Paxos implementation.
"""

# Node states
FOLLOWER = "FOLLOWER"
CANDIDATE = "CANDIDATE"
LEADER = "LEADER"

# Message types from Proposer to Acceptor
PREPARE = "PREPARE"
ACCEPT = "ACCEPT"
HEARTBEAT = "HEARTBEAT"

# Message types from Acceptor to Proposer
PROMISE = "PROMISE"
NOT_PROMISE = "NOT_PROMISE"
ACCEPTED = "ACCEPTED"
NOT_ACCEPTED = "NOT_ACCEPTED"

# Message types from Acceptor to Learner
LEARN = "LEARN"

# Message types between Learners
SYNC_REQUEST = "SYNC_REQUEST"
SYNC_RESPONSE = "SYNC_RESPONSE"
SNAPSHOT_REQUEST = "SNAPSHOT_REQUEST"
SNAPSHOT_RESPONSE = "SNAPSHOT_RESPONSE"
CONSISTENCY_CHECK = "CONSISTENCY_CHECK"
INCONSISTENCY_ALERT = "INCONSISTENCY_ALERT"

# Message types from Client to Proposer/Learner
WRITE_REQUEST = "WRITE_REQUEST"
READ_REQUEST = "READ_REQUEST"
STATUS_REQUEST = "STATUS_REQUEST"

# Message types from Proposer/Learner to Client
WRITE_RESPONSE = "WRITE_RESPONSE"
READ_RESPONSE = "READ_RESPONSE"
STATUS_RESPONSE = "STATUS_RESPONSE"
REDIRECT = "REDIRECT"

# Message types from Client to Learner
SUBSCRIBE = "SUBSCRIBE"
UNSUBSCRIBE = "UNSUBSCRIBE"

# Message types from Learner to Client
NOTIFICATION = "NOTIFICATION"
SUBSCRIPTION_CONFIRMATION = "SUBSCRIPTION_CONFIRMATION"

# Default quorum size calculation
def get_quorum_size(total_nodes):
    """Calculate quorum size based on total nodes."""
    return (total_nodes // 2) + 1
