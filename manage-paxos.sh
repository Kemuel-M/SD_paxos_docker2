#!/bin/bash
# Utility script for managing the Paxos cluster

# Terminal color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to start the cluster
start_cluster() {
    echo -e "${BLUE}Starting Paxos cluster...${NC}"
    docker-compose up -d
    echo -e "${GREEN}Waiting for all services to be ready...${NC}"
    sleep 10
    echo -e "${GREEN}Paxos cluster started!${NC}"
    echo -e "Client interface available at http://localhost:8000/"
}

# Function to stop the cluster
stop_cluster() {
    echo -e "${BLUE}Stopping Paxos cluster...${NC}"
    docker-compose down
    echo -e "${GREEN}Paxos cluster stopped!${NC}"
}

# Function to restart the cluster
restart_cluster() {
    echo -e "${BLUE}Restarting Paxos cluster...${NC}"
    docker-compose restart
    echo -e "${GREEN}Paxos cluster restarted!${NC}"
}

# Function to show cluster status
show_status() {
    echo -e "${BLUE}Paxos cluster status:${NC}"
    docker-compose ps
    
    echo -e "\n${BLUE}Component Health:${NC}"
    
    # Check client health
    client_status=$(curl -s http://localhost:8000/health || echo "Failed to connect")
    echo -e "Client:   ${YELLOW}$client_status${NC}"
    
    # Check proposers health
    proposer1_status=$(curl -s http://localhost:6001/health || echo "Failed to connect")
    proposer2_status=$(curl -s http://localhost:6002/health || echo "Failed to connect")
    echo -e "Proposer1: ${YELLOW}$proposer1_status${NC}"
    echo -e "Proposer2: ${YELLOW}$proposer2_status${NC}"
    
    # Check acceptors health
    acceptor1_status=$(curl -s http://localhost:5001/health || echo "Failed to connect")
    acceptor2_status=$(curl -s http://localhost:5002/health || echo "Failed to connect")
    acceptor3_status=$(curl -s http://localhost:5003/health || echo "Failed to connect")
    echo -e "Acceptor1: ${YELLOW}$acceptor1_status${NC}"
    echo -e "Acceptor2: ${YELLOW}$acceptor2_status${NC}"
    echo -e "Acceptor3: ${YELLOW}$acceptor3_status${NC}"
    
    # Check learners health
    learner1_status=$(curl -s http://localhost:7001/health || echo "Failed to connect")
    learner2_status=$(curl -s http://localhost:7002/health || echo "Failed to connect")
    echo -e "Learner1: ${YELLOW}$learner1_status${NC}"
    echo -e "Learner2: ${YELLOW}$learner2_status${NC}"
}

# Function to run tests
run_tests() {
    echo -e "${BLUE}Running tests on Paxos cluster...${NC}"
    python3 test-paxos.py
}

# Function to view logs
view_logs() {
    component=$1
    if [ -z "$component" ]; then
        echo -e "${BLUE}Viewing all logs:${NC}"
        docker-compose logs -f
    else
        echo -e "${BLUE}Viewing logs for $component:${NC}"
        docker-compose logs -f $component
    fi
}

# Function to simulate failure
simulate_failure() {
    component=$1
    if [ -z "$component" ]; then
        echo -e "${RED}Error: Please specify a component to fail (acceptor1, proposer1, etc.)${NC}"
        return 1
    fi
    
    echo -e "${YELLOW}Simulating failure of $component...${NC}"
    docker-compose stop $component
    echo -e "${GREEN}$component stopped. System should recover automatically.${NC}"
    echo -e "${YELLOW}Run './manage-paxos.sh status' to check system status.${NC}"
}

# Function to recover from failure
recover_component() {
    component=$1
    if [ -z "$component" ]; then
        echo -e "${RED}Error: Please specify a component to recover (acceptor1, proposer1, etc.)${NC}"
        return 1
    fi
    
    echo -e "${BLUE}Recovering $component...${NC}"
    docker-compose start $component
    echo -e "${GREEN}$component started. System should incorporate it automatically.${NC}"
    echo -e "${YELLOW}Run './manage-paxos.sh status' to check system status.${NC}"
}

# Function to rebuild and restart
rebuild() {
    echo -e "${BLUE}Rebuilding Paxos cluster...${NC}"
    docker-compose down
    docker-compose build
    docker-compose up -d
    echo -e "${GREEN}Paxos cluster rebuilt and started!${NC}"
}

# Main script logic
case "$1" in
    start)
        start_cluster
        ;;
    stop)
        stop_cluster
        ;;
    restart)
        restart_cluster
        ;;
    status)
        show_status
        ;;
    test)
        run_tests
        ;;
    logs)
        view_logs $2
        ;;
    fail)
        simulate_failure $2
        ;;
    recover)
        recover_component $2
        ;;
    rebuild)
        rebuild
        ;;
    *)
        echo -e "${BLUE}Paxos Cluster Management Utility${NC}"
        echo -e "Usage: $0 {start|stop|restart|status|test|logs|fail|recover|rebuild}"
        echo -e "  start      - Start the Paxos cluster"
        echo -e "  stop       - Stop the Paxos cluster"
        echo -e "  restart    - Restart the Paxos cluster"
        echo -e "  status     - Show cluster status"
        echo -e "  test       - Run tests on the cluster"
        echo -e "  logs [comp] - View logs (optionally for a specific component)"
        echo -e "  fail <comp> - Simulate failure of a component"
        echo -e "  recover <comp> - Recover a failed component"
        echo -e "  rebuild    - Rebuild and restart the cluster"
        exit 1
        ;;
esac

exit 0
