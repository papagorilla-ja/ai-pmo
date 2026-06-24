#!/bin/bash

# Get the directory of this script
DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$DIR"

echo "=== Starting AI-PMO Infrastructure (Docker) ==="
docker compose up -d

echo "=== Starting Backend (FastAPI) ==="
cd "$DIR/backend"
# Create log file
touch backend.log
# Run backend in background
./venv/bin/python run.py > backend.log 2>&1 &
BACKEND_PID=$!
echo "Backend started with PID: $BACKEND_PID (Logs: backend/backend.log)"

echo "=== Starting Frontend (Vite) ==="
cd "$DIR/frontend"
# Create log file
touch frontend.log
# Run frontend dev in background
npm run dev > frontend.log 2>&1 &
FRONTEND_PID=$!
echo "Frontend started with PID: $FRONTEND_PID (Logs: frontend/frontend.log)"

echo ""
echo "=== System Status ==="
echo "Backend:    http://localhost:8008"
echo "Frontend:   http://localhost:5174"
echo "PostgreSQL: localhost:5435"
echo "Qdrant:     localhost:6335"
echo ""
echo "Use ./stop.sh to stop the services."
