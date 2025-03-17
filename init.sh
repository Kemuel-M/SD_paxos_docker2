#!/bin/bash
# wait-for-it.sh - Wait for a service to be available on a host and port
# Modified from https://github.com/vishnubob/wait-for-it

TIMEOUT=15
QUIET=0

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
  for i in `seq $TIMEOUT` ; do
    nc -z "$HOST" "$PORT" > /dev/null 2>&1
    
    result=$?
    if [ $result -eq 0 ] ; then
      if [ $# -gt 0 ] ; then
        exec "$@"
      fi
      exit 0
    fi
    sleep 1
  done
  echo "Operation timed out" >&2
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

wait_for "$@"
