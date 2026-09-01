#!/bin/bash
# Runs the Billing & Insurance database, backend, and frontend all at once
# for local testing, without Docker.
#
# Usage:
#   cd 4-samarra-billing
#   bash run_local.sh
#
# Ctrl+C stops all three.

set -e

cd "$(dirname "$0")"

echo "=== Preparing local frontend (copying css/ next to index.html) ==="
mkdir -p frontend/templates/css
cp -r frontend/css/* frontend/templates/css/

echo "=== Seeding database ==="
export DB_DATA_DIR="$(pwd)/database/data"
python3 database/init_db.py

echo "=== Starting database (port 6004) ==="
python3 database/app.py &
DB_PID=$!

sleep 1

echo "=== Starting backend (port 5004) ==="
export DATABASE_SERVICE_URL="http://localhost:6004"
export OLLAMA_BASE_URL="http://localhost:11434/v1"
export OLLAMA_MODEL="qwen2.5:0.5b"
python3 backend/app.py &
BACKEND_PID=$!

sleep 1

echo "=== Starting frontend (port 3004) ==="
(cd frontend/templates && python3 -m http.server 3004) &
FRONTEND_PID=$!

echo ""
echo "Billing stack is running:"
echo "  Database:  http://localhost:6004"
echo "  Backend:   http://localhost:5004"
echo "  Frontend:  http://localhost:3004/index.html"
echo ""
echo "Note: AI chat requires Ollama running locally with qwen2.5:0.5b pulled."
echo "  Check with: ollama list"
echo ""
echo "Press Ctrl+C to stop everything."

trap "echo ''; echo 'Stopping...'; kill $DB_PID $BACKEND_PID $FRONTEND_PID 2>/dev/null" EXIT INT TERM

wait