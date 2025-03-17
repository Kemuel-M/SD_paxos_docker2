"""
Main entry point for Learner service.
"""

import os
import json
import atexit
import random
from flask import Flask, request, jsonify

from learner import Learner
from common.utils import setup_logger, parse_hosts
from common.constants import get_quorum_size

# Get environment variables
LEARNER_ID = os.environ.get('LEARNER_ID', '1')
LEARNER_PORT = int(os.environ.get('LEARNER_PORT', 7001))
ACCEPTOR_HOSTS_STR = os.environ.get('ACCEPTOR_HOSTS', 'acceptor1:5001,acceptor2:5002,acceptor3:5003')
PROPOSER_HOSTS_STR = os.environ.get('PROPOSER_HOSTS', 'proposer1:6001,proposer2:6002')
OTHER_LEARNERS_STR = os.environ.get('OTHER_LEARNERS', None)
TOTAL_ACCEPTORS = int(os.environ.get('TOTAL_ACCEPTORS', 3))
QUORUM_SIZE = int(os.environ.get('QUORUM_SIZE', get_quorum_size(TOTAL_ACCEPTORS)))
DATA_DIR = os.environ.get('DATA_DIR', '/data')

# Parse hosts
ACCEPTOR_HOSTS = parse_hosts(ACCEPTOR_HOSTS_STR)
PROPOSER_HOSTS = parse_hosts(PROPOSER_HOSTS_STR)

# Parse other learners (exclude self)
OTHER_LEARNERS = []
if OTHER_LEARNERS_STR:
    all_learners = parse_hosts(OTHER_LEARNERS_STR)
    OTHER_LEARNERS = [(host, port) for host, port in all_learners 
                     if f"{host}:{port}" != f"learner{LEARNER_ID}:{LEARNER_PORT}"]
else:
    # Infer other learners from the environment
    learner_prefix = 'learner'
    for i in range(1, 10):  # Assume max 10 learners
        if str(i) != LEARNER_ID:
            OTHER_LEARNERS.append((f"{learner_prefix}{i}", 7000 + i))

# Set up Flask application
app = Flask(__name__)
logger = setup_logger(f"learner-{LEARNER_ID}-api")

# Initialize learner instance
learner = Learner(LEARNER_ID, DATA_DIR, ACCEPTOR_HOSTS, OTHER_LEARNERS, TOTAL_ACCEPTORS, QUORUM_SIZE)

# Register shutdown function
atexit.register(lambda: learner.stop())

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok", 
        "learner_id": LEARNER_ID,
        "last_applied": learner.last_applied,
        "highest_seen": learner.highest_seen
    })

@app.route('/status', methods=['GET'])
def status():
    """Get learner status."""
    try:
        status_info = learner.get_status()
        return jsonify(status_info)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/learn', methods=['POST'])
def learn():
    """Handle learn messages from acceptors."""
    try:
        data = request.json
        logger.debug(f"Received learn message: {data}")
        
        response = learner.handle_learn(data)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling learn message: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/sync', methods=['POST'])
def sync():
    """Handle synchronization requests from other learners."""
    try:
        data = request.json
        logger.debug(f"Received sync request: {data}")
        
        response = learner.handle_sync_request(data)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling sync request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/read', methods=['POST'])
def read():
    """Handle read requests from clients."""
    try:
        data = request.json
        logger.debug(f"Received read request: {data}")
        
        response = learner.handle_read_request(data)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling read request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/subscribe', methods=['POST'])
def subscribe():
    """Handle subscription requests from clients."""
    try:
        data = request.json
        logger.debug(f"Received subscribe request: {data}")
        
        response = learner.handle_subscribe(data)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling subscribe request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    """Handle unsubscribe requests from clients."""
    try:
        data = request.json
        logger.debug(f"Received unsubscribe request: {data}")
        
        response = learner.handle_unsubscribe(data)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling unsubscribe request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/state', methods=['GET'])
def get_state():
    """Get current application state."""
    try:
        return jsonify({
            "state": learner.application_state,
            "version": learner.last_applied,
            "timestamp": time.time()
        })
    except Exception as e:
        logger.error(f"Error getting application state: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Starting Learner {LEARNER_ID} on port {LEARNER_PORT}")
    app.run(host='0.0.0.0', port=LEARNER_PORT, debug=False)
