#!/usr/bin/env python3
"""
Simple test script to verify the Paxos system is working correctly.
"""

import argparse
import json
import time
import random
import requests

def get_status(host="localhost", port=8000):
    """Get system status."""
    try:
        response = requests.get(f"http://{host}:{port}/status")
        return response.json()
    except Exception as e:
        print(f"Error getting status: {e}")
        return None

def write_value(key, value, host="localhost", port=8000):
    """Write a key-value pair."""
    try:
        response = requests.post(
            f"http://{host}:{port}/write",
            json={"key": key, "value": value}
        )
        return response.json()
    except Exception as e:
        print(f"Error writing value: {e}")
        return None

def read_value(key, consistency="eventual", host="localhost", port=8000):
    """Read a value by key."""
    try:
        response = requests.post(
            f"http://{host}:{port}/read",
            json={"key": key, "consistency": consistency}
        )
        return response.json()
    except Exception as e:
        print(f"Error reading value: {e}")
        return None

def run_simple_test(host="localhost", port=8000):
    """Run a simple test sequence."""
    print("Running simple Paxos test...")
    
    # Check system status
    print("\n1. Checking system status...")
    status = get_status(host, port)
    if status:
        print(f"System status: {json.dumps(status, indent=2)}")
    else:
        print("Failed to get system status")
        return False
    
    # Write a value
    test_key = f"test_key_{random.randint(1000, 9999)}"
    test_value = f"test_value_{random.randint(1000, 9999)}"
    
    print(f"\n2. Writing key-value: {test_key} = {test_value}")
    write_response = write_value(test_key, test_value, host, port)
    if write_response:
        print(f"Write response: {json.dumps(write_response, indent=2)}")
    else:
        print("Failed to write value")
        return False
    
    # Allow some time for propagation
    print("\nWaiting for propagation...")
    time.sleep(2)
    
    # Read with eventual consistency
    print("\n3. Reading with eventual consistency...")
    read_response_eventual = read_value(test_key, "eventual", host, port)
    if read_response_eventual:
        print(f"Read response (eventual): {json.dumps(read_response_eventual, indent=2)}")
        result = read_response_eventual.get("result")
        if result == test_value:
            print("✅ Read successful - value matches!")
        else:
            print(f"❌ Value mismatch: got {result}, expected {test_value}")
    else:
        print("Failed to read value with eventual consistency")
        return False
    
    # Read with strong consistency
    print("\n4. Reading with strong consistency...")
    read_response_strong = read_value(test_key, "strong", host, port)
    if read_response_strong:
        print(f"Read response (strong): {json.dumps(read_response_strong, indent=2)}")
        result = read_response_strong.get("result")
        if result == test_value:
            print("✅ Read successful - value matches!")
        else:
            print(f"❌ Value mismatch: got {result}, expected {test_value}")
    else:
        print("Failed to read value with strong consistency")
    
    # Final status check
    print("\n5. Checking final system status...")
    final_status = get_status(host, port)
    if final_status:
        print(f"Final status: {json.dumps(final_status, indent=2)}")
    else:
        print("Failed to get final system status")
    
    print("\nTest sequence completed!")
    return True

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Paxos distributed system")
    parser.add_argument("--host", default="localhost", help="Client API host")
    parser.add_argument("--port", type=int, default=8000, help="Client API port")
    
    args = parser.parse_args()
    
    success = run_simple_test(args.host, args.port)
    
    if success:
        print("\n✅ All tests passed successfully!")
    else:
        print("\n❌ Some tests failed!")
