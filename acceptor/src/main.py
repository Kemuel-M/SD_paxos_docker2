"""
Main entry point for Acceptor service.
"""

import os
import json
from flask import Flask, request, jsonify

from acceptor import Acceptor
from common.message import (
    PrepareMessage, AcceptMessage, HeartbeatMessage
)
from common.constants import PREPARE, ACCEPT, HEARTBEAT
from common.utils import setup_logger

# Get environment variables
ACCEPTOR_ID = os.environ.get('ACCEPTOR_ID', '1')
ACCEPTOR_PORT = int(os.environ.get('ACCEPTOR_PORT', 5001))
TOTAL_ACCEPTORS = int(os.environ.get('TOTAL_ACCEPTORS', 3))
DATA_DIR = os.environ.get('DATA_DIR', '/data')

# Set up Flask application
app = Flask(__name__)
logger = setup_logger(f"acceptor-{ACCEPTOR_ID}-api")

# Initialize acceptor instance
acceptor = Acceptor(ACCEPTOR_ID, DATA_DIR, TOTAL_ACCEPTORS)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({"status": "ok", "acceptor_id": ACCEPTOR_ID})

@app.route('/prepare', methods=['POST'])
def prepare():
    """Handle prepare requests."""
    try:
        data = request.json
        logger.debug(f"Received prepare request: {data}")
        
        prepare_msg = PrepareMessage(
            type=PREPARE,
            proposal_number=data['proposal_number'],
            proposer_id=data['proposer_id']
        )
        
        response = acceptor.handle_prepare(prepare_msg)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling prepare request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/accept', methods=['POST'])
def accept():
    """Handle accept requests."""
    try:
        data = request.json
        logger.debug(f"Received accept request: {data}")
        
        accept_msg = AcceptMessage(
            type=ACCEPT,
            proposal_number=data['proposal_number'],
            value=data['value'],
            proposer_id=data['proposer_id']
        )
        
        response = acceptor.handle_accept(accept_msg)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling accept request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/heartbeat', methods=['POST'])
def heartbeat():
    """Handle heartbeat messages."""
    try:
        data = request.json
        logger.debug(f"Received heartbeat: {data}")
        
        heartbeat_msg = HeartbeatMessage(
            type=HEARTBEAT,
            leader_id=data['leader_id'],
            sequence_number=data['sequence_number'],
            timestamp=data['timestamp']
        )
        
        response = acceptor.handle_heartbeat(heartbeat_msg)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling heartbeat: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/status', methods=['GET'])
def status():
    """Get acceptor status."""
    try:
        status_info = {
            "acceptor_id": ACCEPTOR_ID,
            "max_promised": acceptor.max_promised,
            "max_accepted": acceptor.max_accepted,
            "has_accepted_value": acceptor.accepted_value is not None,
            "current_leader": acceptor.current_leader_id
        }
        return jsonify(status_info)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Starting Acceptor {ACCEPTOR_ID} on port {ACCEPTOR_PORT}")
    app.run(host='0.0.0.0', port=ACCEPTOR_PORT, debug=False)
