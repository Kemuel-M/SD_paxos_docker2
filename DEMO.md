# Paxos Distributed System Demo

This document provides a step-by-step demonstration of the Paxos distributed system implemented in this project.

## Setup and Basic Operations

### Starting the Cluster

```bash
# Clone the repository
git clone <repository-url>
cd paxos-network

# Make the management script executable
chmod +x manage-paxos.sh

# Start the cluster
./manage-paxos.sh start
```

### Checking Cluster Status

```bash
# Check the status of all components
./manage-paxos.sh status

# View logs of all components
./manage-paxos.sh logs

# View logs of a specific component
./manage-paxos.sh logs proposer1
```

## Web Interface

The client component provides a web interface at http://localhost:8000/

1. Open your browser and navigate to http://localhost:8000/
2. Use the interface to:
   - Write key-value pairs to the system
   - Read values with different consistency levels
   - Check the system status

## Command Line Operations

### Running the Test Script

```bash
# Run the automated test script
python3 test-paxos.py
```

### Manual Operations with curl

#### Write a value:

```bash
curl -X POST http://localhost:8000/write \
  -H "Content-Type: application/json" \
  -d '{"key": "mykey", "value": "myvalue"}'
```

#### Read a value:

```bash
curl -X POST http://localhost:8000/read \
  -H "Content-Type: application/json" \
  -d '{"key": "mykey", "consistency": "eventual"}'
```

#### Check system status:

```bash
curl http://localhost:8000/status
```

## Fault Tolerance Demonstration

### Simulating Node Failures

#### 1. Acceptor Failure (Tolerable)

```bash
# Check current status
./manage-paxos.sh status

# Simulate failure of one acceptor
./manage-paxos.sh fail acceptor1

# Test the system - should still work with 2/3 acceptors
python3 test-paxos.py

# Recover the failed acceptor
./manage-paxos.sh recover acceptor1
```

#### 2. Multiple Acceptor Failures (Non-tolerable)

```bash
# Simulate failure of two acceptors
./manage-paxos.sh fail acceptor1
./manage-paxos.sh fail acceptor2

# Test the system - should fail without quorum
python3 test-paxos.py

# Recover the failed acceptors
./manage-paxos.sh recover acceptor1
./manage-paxos.sh recover acceptor2
```

#### 3. Leader Proposer Failure

```bash
# Check which proposer is the leader
curl http://localhost:6001/status
curl http://localhost:6002/status

# Simulate failure of the leader proposer
./manage-paxos.sh fail proposer1  # Assuming proposer1 is the leader

# Wait for new leader election
sleep 5

# Check new leader status
curl http://localhost:6002/status

# Test the system - should work with new leader
python3 test-paxos.py

# Recover the failed proposer
./manage-paxos.sh recover proposer1
```

#### 4. Learner Failure

```bash
# Simulate failure of one learner
./manage-paxos.sh fail learner1

# Test the system - should work with remaining learner
python3 test-paxos.py

# Recover the failed learner
./manage-paxos.sh recover learner1

# Watch the learner sync logs to catch up
./manage-paxos.sh logs learner1
```

## Key Paxos Properties Demonstration

### Safety: Only one value is chosen

1. Write a value to a key
2. Check that all learners report the same value for that key

```bash
# Write value
curl -X POST http://localhost:8000/write -H "Content-Type: application/json" -d '{"key": "safetyTest", "value": "initialValue"}'

# Check value on learner1
curl -X POST http://localhost:7001/read -H "Content-Type: application/json" -d '{"key": "safetyTest", "consistency_level": "eventual", "client_id": "testclient"}'

# Check value on learner2
curl -X POST http://localhost:7002/read -H "Content-Type: application/json" -d '{"key": "safetyTest", "consistency_level": "eventual", "client_id": "testclient"}'
```

### Liveness: Progress can be made despite failures

1. Write a value
2. Simulate failure of a non-leader proposer (system continues)
3. Write another value
4. Simulate failure of a single acceptor (system continues)
5. Write a third value

```bash
# Initial write
curl -X POST http://localhost:8000/write -H "Content-Type: application/json" -d '{"key": "livenessTest", "value": "value1"}'

# Fail non-leader proposer
./manage-paxos.sh fail proposer2  # Assuming proposer2 is not the leader

# Write another value
curl -X POST http://localhost:8000/write -H "Content-Type: application/json" -d '{"key": "livenessTest", "value": "value2"}'

# Fail one acceptor
./manage-paxos.sh fail acceptor3

# Write a third value
curl -X POST http://localhost:8000/write -H "Content-Type: application/json" -d '{"key": "livenessTest", "value": "value3"}'

# Check final value
curl -X POST http://localhost:8000/read -H "Content-Type: application/json" -d '{"key": "livenessTest", "consistency": "strong"}'

# Recover all components
./manage-paxos.sh recover proposer2
./manage-paxos.sh recover acceptor3
```

## Cleaning Up

```bash
# Stop the cluster
./manage-paxos.sh stop
```

## Advanced Features

### Different Consistency Levels

Demonstrate the difference between consistency levels:

```bash
# Write a value
curl -X POST http://localhost:8000/write -H "Content-Type: application/json" -d '{"key": "consistencyTest", "value": "testValue"}'

# Read with eventual consistency (fastest, potentially stale)
curl -X POST http://localhost:8000/read -H "Content-Type: application/json" -d '{"key": "consistencyTest", "consistency": "eventual"}'

# Read with session consistency (client sees its own writes)
curl -X POST http://localhost:8000/read -H "Content-Type: application/json" -d '{"key": "consistencyTest", "consistency": "session"}'

# Read with strong consistency (linearizable, through leader)
curl -X POST http://localhost:8000/read -H "Content-Type: application/json" -d '{"key": "consistencyTest", "consistency": "strong"}'
```

### Subscription for Notifications

```bash
# Subscribe to notifications for keys matching a pattern
curl -X POST http://localhost:8000/subscribe -H "Content-Type: application/json" -d '{"patterns": ["notify*"]}'

# Write to a matching key to trigger notification
curl -X POST http://localhost:8000/write -H "Content-Type: application/json" -d '{"key": "notifyTest", "value": "notificationValue"}'

# Unsubscribe (replace with actual subscription ID from subscribe response)
curl -X POST http://localhost:8000/unsubscribe -H "Content-Type: application/json" -d '{"subscription_id": "subscription-uuid-from-response"}'
```
