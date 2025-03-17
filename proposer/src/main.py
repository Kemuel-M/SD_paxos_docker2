"""
Main entry point for Proposer service.
"""

import os
import json
import atexit
from flask import Flask, request, jsonify

from proposer import Proposer
from common.utils import setup_logger, parse_hosts

# Get environment variables
PROPOSER_ID = os.environ.get('PROPOSER_ID', '1')
PROPOSER_PORT = int(os.environ.get('PROPOSER_PORT', 6001))
ACCEPTOR_HOSTS_STR = os.environ.get('ACCEPTOR_HOSTS', 'acceptor1:5001,acceptor2:5002,acceptor3:5003')
LEARNER_HOSTS_STR = os.environ.get('LEARNER_HOSTS', 'learner1:7001,learner2:7002')
HEARTBEAT_INTERVAL = int(os.environ.get('HEARTBEAT_INTERVAL', 500))  # in ms
LEADER_TIMEOUT = int(os.environ.get('LEADER_TIMEOUT', 1500))  # in ms

# Parse hosts
ACCEPTOR_HOSTS = parse_hosts(ACCEPTOR_HOSTS_STR)
LEARNER_HOSTS = parse_hosts(LEARNER_HOSTS_STR)

# Set up Flask application
app = Flask(__name__)
logger = setup_logger(f"proposer-{PROPOSER_ID}-api")

# Initialize proposer instance
proposer = Proposer(PROPOSER_ID, ACCEPTOR_HOSTS, LEARNER_HOSTS, 
                  HEARTBEAT_INTERVAL, LEADER_TIMEOUT)

# Register shutdown function
atexit.register(lambda: proposer.stop())

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok", 
        "proposer_id": PROPOSER_ID,
        "state": proposer.state,
        "leader_id": proposer.leader_id or "unknown"
    })

@app.route('/status', methods=['GET'])
def status():
    """Get proposer status."""
    try:
        status_info = {
            "proposer_id": PROPOSER_ID,
            "state": proposer.state,
            "leader_id": proposer.leader_id,
            "is_leader": proposer.state == "LEADER",
            "last_heartbeat": proposer.last_heartbeat,
            "active_proposals": len(proposer.active_proposals),
            "queued_proposals": len(proposer.proposal_queue)
        }
        return jsonify(status_info)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/request', methods=['POST'])
def handle_request():
    """Handle client requests."""
    try:
        data = request.json
        logger.debug(f"Received client request: {data}")
        
        response = proposer.handle_client_request(data)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling client request: {e}")
        return jsonify({
            "type": "ERROR",
            "request_id": data.get('request_id') if 'data' in locals() else None,
            "error": str(e)
        }), 500

@app.route('/prepare_test', methods=['POST'])
def prepare_test():
    """Test endpoint to manually trigger prepare phase."""
    try:
        proposer._start_election()
        return jsonify({"status": "prepare_started"})
    except Exception as e:
        logger.error(f"Error starting prepare test: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Starting Proposer {PROPOSER_ID} on port {PROPOSER_PORT}")
    app.run(host='0.0.0.0', port=PROPOSER_PORT, debug=False)
