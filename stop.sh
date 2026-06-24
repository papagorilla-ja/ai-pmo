#!/bin/bash

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"

echo "=== Stopping AI-PMO Web Services ==="

# Find and kill backend on port 8008
BACKEND_PIDS=$(lsof -t -i :8008)
if [ -n "$BACKEND_PIDS" ]; then
  echo "Stopping Backend processes (PIDs: $BACKEND_PIDS)..."
  kill $BACKEND_PIDS 2>/dev/null
else
  echo "Backend is not running on port 8008."
fi

# Find and kill frontend on port 5174
FRONTEND_PIDS=$(lsof -t -i :5174)
if [ -n "$FRONTEND_PIDS" ]; then
  echo "Stopping Frontend processes (PIDs: $FRONTEND_PIDS)..."
  kill $FRONTEND_PIDS 2>/dev/null
else
  echo "Frontend is not running on port 5174."
fi

echo "=== Stopping Docker Infrastructure ==="
cd "$DIR"
docker compose down

echo ""
echo "AI-PMO stopped successfully."
