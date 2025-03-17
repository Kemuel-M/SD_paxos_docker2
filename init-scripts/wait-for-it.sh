#!/bin/bash
# wait-for-it.sh - Wait for a service to be available on a host and port
# Modified from https://github.com/vishnubob/wait-for-it

# Longer default timeout (60 seconds instead of 15)
TIMEOUT=60
QUIET=0

# Make sure netcat is installed
which nc > /dev/null || { echo "Error: netcat (nc) is not installed"; exit 1; }

usage() {
  cat << EOF
Usage: $0 host:port [-t timeout] [-- command args]
-t TIMEOUT     Timeout in seconds, default is $TIMEOUT
-q             Quiet mode
-- COMMAND ARGS   Command with args to run after the service is available
EOF
  exit 1
}

wait_for() {
  echo "Waiting for $HOST:$PORT for up to $TIMEOUT seconds..."
  
  for i in `seq $TIMEOUT` ; do
    # Attempt connection with 2 second timeout
    nc -z -w 2 "$HOST" "$PORT" > /dev/null 2>&1
    
    result=$?
    if [ $result -eq 0 ] ; then
      echo "Service $HOST:$PORT is now available"
      if [ $# -gt 0 ] ; then
        exec "$@"
      fi
      exit 0
    fi
    sleep 1
    
    # Print a progress message every 10 seconds
    if [ $(($i % 10)) -eq 0 ]; then
      echo "Still waiting for $HOST:$PORT... ($i/$TIMEOUT)"
    fi
  done
  
  echo "ERROR: Operation timed out waiting for $HOST:$PORT after $TIMEOUT seconds" >&2
  exit 1
}

while getopts ":t:q" opt; do
  case "$opt" in
    t) TIMEOUT="$OPTARG" ;;
    q) QUIET=1 ;;
    \?) echo "Invalid option: -$OPTARG" >&2; usage ;;
    :) echo "Option -$OPTARG requires an argument." >&2; usage ;;
  esac
done

shift $((OPTIND-1))

if [ "$#" -eq 0 ]; then
  usage
fi

HOST=$(printf "%s\n" "$1"| cut -d : -f 1)
PORT=$(printf "%s\n" "$1"| cut -d : -f 2)
shift

if [ "$HOST" = "" -o "$PORT" = "" ]; then
  echo "Error: you need to provide a host and port to test."
  usage
fi

# Add delay before starting to wait
echo "Waiting 5 seconds before starting connection tests..."
sleep 5

wait_for "$@"