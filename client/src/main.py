"""
Main entry point for Client service.
"""

import os
import json
import atexit
from flask import Flask, request, jsonify, render_template_string

from client import PaxosClient
from common.utils import setup_logger, parse_hosts

# Get environment variables
CLIENT_ID = os.environ.get('CLIENT_ID', 'client1')
CLIENT_PORT = int(os.environ.get('CLIENT_PORT', 8000))
PROPOSER_HOSTS_STR = os.environ.get('PROPOSER_HOSTS', 'proposer1:6001,proposer2:6002')
LEARNER_HOSTS_STR = os.environ.get('LEARNER_HOSTS', 'learner1:7001,learner2:7002')

# Parse hosts
PROPOSER_HOSTS = parse_hosts(PROPOSER_HOSTS_STR)
LEARNER_HOSTS = parse_hosts(LEARNER_HOSTS_STR)

# Set up Flask application
app = Flask(__name__)
logger = setup_logger(f"client-{CLIENT_ID}-api")

# Initialize client instance
client = PaxosClient(CLIENT_ID, PROPOSER_HOSTS, LEARNER_HOSTS)

# Register shutdown function
atexit.register(lambda: client.stop())

# Simple HTML template for the web interface
INDEX_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Paxos Client Interface</title>
    <style>
        body {
            font-family: Arial, sans-serif;
            margin: 20px;
            line-height: 1.6;
        }
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        h1 {
            color: #333;
            border-bottom: 1px solid #ddd;
            padding-bottom: 10px;
        }
        .section {
            margin: 20px 0;
            padding: 15px;
            background-color: #f8f8f8;
            border-radius: 5px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
        }
        input[type="text"], select {
            width: 100%;
            padding: 8px;
            border: 1px solid #ddd;
            border-radius: 4px;
        }
        button {
            background-color: #4CAF50;
            color: white;
            padding: 10px 15px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
        }
        button:hover {
            background-color: #45a049;
        }
        pre {
            background-color: #f1f1f1;
            padding: 10px;
            border-radius: 4px;
            overflow-x: auto;
        }
        .response {
            margin-top: 15px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Paxos Client Interface</h1>
        
        <div class="section">
            <h2>Write to Paxos</h2>
            <form id="writeForm">
                <div class="form-group">
                    <label for="writeKey">Key:</label>
                    <input type="text" id="writeKey" name="key" required>
                </div>
                <div class="form-group">
                    <label for="writeValue">Value:</label>
                    <input type="text" id="writeValue" name="value" required>
                </div>
                <button type="submit">Write</button>
            </form>
            <div class="response">
                <h3>Response:</h3>
                <pre id="writeResponse">No response yet</pre>
            </div>
        </div>
        
        <div class="section">
            <h2>Read from Paxos</h2>
            <form id="readForm">
                <div class="form-group">
                    <label for="readKey">Key:</label>
                    <input type="text" id="readKey" name="key" required>
                </div>
                <div class="form-group">
                    <label for="consistency">Consistency Level:</label>
                    <select id="consistency" name="consistency">
                        <option value="eventual">Eventual</option>
                        <option value="session">Session</option>
                        <option value="strong">Strong</option>
                    </select>
                </div>
                <button type="submit">Read</button>
            </form>
            <div class="response">
                <h3>Response:</h3>
                <pre id="readResponse">No response yet</pre>
            </div>
        </div>
        
        <div class="section">
            <h2>System Status</h2>
            <button id="statusButton">Get Status</button>
            <div class="response">
                <h3>Response:</h3>
                <pre id="statusResponse">No response yet</pre>
            </div>
        </div>
    </div>
    
    <script>
        document.getElementById('writeForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const key = document.getElementById('writeKey').value;
            const value = document.getElementById('writeValue').value;
            
            fetch('/write', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ key, value }),
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('writeResponse').textContent = JSON.stringify(data, null, 2);
            })
            .catch(error => {
                document.getElementById('writeResponse').textContent = 'Error: ' + error;
            });
        });
        
        document.getElementById('readForm').addEventListener('submit', function(e) {
            e.preventDefault();
            const key = document.getElementById('readKey').value;
            const consistency = document.getElementById('consistency').value;
            
            fetch('/read', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ key, consistency }),
            })
            .then(response => response.json())
            .then(data => {
                document.getElementById('readResponse').textContent = JSON.stringify(data, null, 2);
            })
            .catch(error => {
                document.getElementById('readResponse').textContent = 'Error: ' + error;
            });
        });
        
        document.getElementById('statusButton').addEventListener('click', function() {
            fetch('/status')
            .then(response => response.json())
            .then(data => {
                document.getElementById('statusResponse').textContent = JSON.stringify(data, null, 2);
            })
            .catch(error => {
                document.getElementById('statusResponse').textContent = 'Error: ' + error;
            });
        });
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    """Display the web interface."""
    return render_template_string(INDEX_TEMPLATE)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "ok", 
        "client_id": CLIENT_ID
    })

@app.route('/status', methods=['GET'])
def status():
    """Get cluster status."""
    try:
        status_info = client.get_status()
        
        # Add client specific info
        status_info.update({
            "client_id": CLIENT_ID,
            "highest_seen_sequence": client.highest_seen_sequence,
            "pending_requests": len(client.pending_requests),
            "retry_queue": len(client.retry_queue)
        })
        
        return jsonify(status_info)
    except Exception as e:
        logger.error(f"Error getting status: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/write', methods=['POST'])
def write():
    """Handle write requests."""
    try:
        data = request.json
        key = data.get('key')
        value = data.get('value')
        
        if not key:
            return jsonify({"error": "Key is required"}), 400
        
        logger.info(f"Received write request: key={key}, value={value}")
        
        response = client.write(key, value)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling write request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/read', methods=['POST'])
def read():
    """Handle read requests."""
    try:
        data = request.json
        key = data.get('key')
        consistency = data.get('consistency', 'eventual')
        
        if not key:
            return jsonify({"error": "Key is required"}), 400
        
        logger.info(f"Received read request: key={key}, consistency={consistency}")
        
        response = client.read(key, consistency)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling read request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/subscribe', methods=['POST'])
def subscribe():
    """Handle subscription requests."""
    try:
        data = request.json
        patterns = data.get('patterns', [])
        
        if not patterns:
            return jsonify({"error": "Patterns are required"}), 400
        
        logger.info(f"Received subscribe request with patterns: {patterns}")
        
        response = client.subscribe(patterns)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling subscribe request: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/unsubscribe', methods=['POST'])
def unsubscribe():
    """Handle unsubscribe requests."""
    try:
        data = request.json
        subscription_id = data.get('subscription_id')
        
        if not subscription_id:
            return jsonify({"error": "Subscription ID is required"}), 400
        
        logger.info(f"Received unsubscribe request: {subscription_id}")
        
        response = client.unsubscribe(subscription_id)
        return jsonify(response)
    except Exception as e:
        logger.error(f"Error handling unsubscribe request: {e}")
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    logger.info(f"Starting Client {CLIENT_ID} on port {CLIENT_PORT}")
    app.run(host='0.0.0.0', port=CLIENT_PORT, debug=False)
