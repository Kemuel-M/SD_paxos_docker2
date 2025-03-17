# Paxos Distributed Consensus System

This project implements a distributed consensus system based on the Paxos protocol as described in academic literature. It provides a complete implementation of all Paxos components: Acceptors, Proposers, Learners, and Clients.

## Architecture Overview

The system follows the classic Paxos protocol architecture with the following components:

1. **Acceptors**: The memory of the system, responsible for voting on proposals
2. **Proposers**: Responsible for proposing values and coordinating consensus
3. **Learners**: Apply decided values and maintain the consistent state
4. **Clients**: Interface for users to interact with the system

## Project Structure

```
paxos-network/
│
├── docker-compose.yml        # Container orchestration
├── common/                   # Shared code
│   ├── Dockerfile
│   └── src/
│       ├── __init__.py
│       ├── constants.py      # Protocol constants
│       ├── message.py        # Message definitions
│       └── utils.py          # Utility functions
├── acceptor/                 # Acceptor component
│   ├── Dockerfile
│   └── src/
│       ├── __init__.py
│       ├── acceptor.py       # Acceptor implementation
│       └── main.py           # API endpoints
├── proposer/                 # Proposer component
│   ├── Dockerfile
│   └── src/
│       ├── __init__.py
│       ├── proposer.py       # Proposer implementation
│       └── main.py           # API endpoints
├── learner/                  # Learner component
│   ├── Dockerfile
│   └── src/
│       ├── __init__.py
│       ├── learner.py        # Learner implementation
│       └── main.py           # API endpoints
├── client/                   # Client component
│   ├── Dockerfile
│   └── src/
│       ├── __init__.py
│       ├── client.py         # Client implementation
│       └── main.py           # API endpoints
└── README.md                 # This documentation
```

## Implementation Details

### Acceptors

- Maintain persistent state of promises and accepted values
- Participate in both phases of the Paxos protocol
- Handle prepare and accept requests from proposers
- Notify learners when values are accepted

### Proposers

- Generate unique proposal numbers
- Implement leader election via Paxos
- Optimize with Multi-Paxos for better performance
- Maintain heartbeats to detect leader failures

### Learners

- Learn consensus decisions from acceptors
- Apply decisions in order to maintain state
- Provide synchronization mechanisms to fill gaps
- Serve read requests from clients

### Clients

- Interface with the system through a simple REST API
- Provide write and read operations with different consistency levels
- Subscribe to notifications for specific events

## Running the System

### Prerequisites

- Docker and Docker Compose installed
- Network connectivity between containers

### Starting the Cluster

1. Clone the repository
2. Build and start the containers:

```bash
docker-compose up -d
```

This will start a cluster with:
- 3 Acceptors
- 2 Proposers
- 2 Learners
- 1 Client API

### Using the Client API

The client API is accessible at http://localhost:8000/ and provides a simple web interface to interact with the system.

#### REST Endpoints

- `GET /health` - Health check
- `GET /status` - Get system status
- `POST /write` - Write key-value pairs
  ```json
  {
    "key": "mykey",
    "value": "myvalue"
  }
  ```
- `POST /read` - Read values
  ```json
  {
    "key": "mykey",
    "consistency": "eventual"
  }
  ```
- `POST /subscribe` - Subscribe to notifications
  ```json
  {
    "patterns": ["key*"]
  }
  ```
- `POST /unsubscribe` - Unsubscribe from notifications
  ```json
  {
    "subscription_id": "subscription-uuid"
  }
  ```

### Consistency Levels

The system supports different consistency levels for read operations:

- `strong`: Linearizable reads through the leader (slowest but strongest)
- `session`: Session consistency (client sees its own writes)
- `eventual`: Eventual consistency (fastest but weakest)

## Fault Tolerance

The system is designed to be fault-tolerant:

- It tolerates the failure of up to 1 acceptor in a 3-acceptor configuration
- If the leader proposer fails, a new leader is elected automatically
- Learners can catch up after failures by synchronizing with each other

## Environment Variables

Each component can be configured through environment variables:

### Acceptor
- `ACCEPTOR_ID`: Unique identifier
- `ACCEPTOR_PORT`: Port to listen on
- `TOTAL_ACCEPTORS`: Total number of acceptors
- `LOG_LEVEL`: Logging verbosity

### Proposer
- `PROPOSER_ID`: Unique identifier
- `PROPOSER_PORT`: Port to listen on
- `ACCEPTOR_HOSTS`: Comma-separated list of acceptor addresses
- `LEARNER_HOSTS`: Comma-separated list of learner addresses
- `HEARTBEAT_INTERVAL`: Interval between heartbeats in ms
- `LEADER_TIMEOUT`: Time to wait before starting election in ms
- `LOG_LEVEL`: Logging verbosity

### Learner
- `LEARNER_ID`: Unique identifier
- `LEARNER_PORT`: Port to listen on
- `ACCEPTOR_HOSTS`: Comma-separated list of acceptor addresses
- `PROPOSER_HOSTS`: Comma-separated list of proposer addresses
- `TOTAL_ACCEPTORS`: Total number of acceptors
- `QUORUM_SIZE`: Size of quorum for decisions
- `LOG_LEVEL`: Logging verbosity

### Client
- `CLIENT_ID`: Unique identifier
- `CLIENT_PORT`: Port to listen on
- `PROPOSER_HOSTS`: Comma-separated list of proposer addresses
- `LEARNER_HOSTS`: Comma-separated list of learner addresses
- `LOG_LEVEL`: Logging verbosity

## Testing and Development

To inspect the logs:

```bash
docker-compose logs -f
```

To get logs for a specific service:

```bash
docker-compose logs -f acceptor1
```

## Protocol Details

This implementation follows the standard Paxos protocol as described in the provided documents, with optimizations for practical use:

1. **Basic Paxos** for the fundamental consensus algorithm
2. **Multi-Paxos** for performance optimization (skipping Phase 1 when possible)
3. **Leader Election** via Paxos for coordination
4. **Heartbeats** for failure detection

## Future Improvements

- Add authentication and encryption for security
- Implement dynamic membership changes
- Add metrics and monitoring
- Improve performance with batching and pipelining
