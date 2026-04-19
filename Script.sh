#!/usr/bin/env bash
set -euo pipefail

echo "Photon Safe Startup"

# Use the directory this script is stored in
PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
VENV_DIR="$PROJECT_DIR/venv"

echo "Project dir: $PROJECT_DIR"
echo "Venv dir:    $VENV_DIR"
echo ""

cd "$PROJECT_DIR"

# 1) Install only required system packages
sudo apt update
sudo apt install -y \
  python3 \
  python3-venv \
  python3-tk \
  python3-pip \
  postgresql \
  postgresql-contrib

# 2) Start PostgreSQL service only
sudo systemctl enable postgresql
sudo systemctl restart postgresql

# 3) Create venv in the Photon project folder if missing
if [ ! -d "$VENV_DIR" ]; then
  python3 -m venv "$VENV_DIR"
fi

# 4) Activate venv and install Python dependencies
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip
python -m pip install psycopg2-binary Pillow pygame

echo ""
echo "Environment ready."
echo "Working directory: $(pwd)"
echo ""

# 5) Verify expected files exist before launching
required_files=(
  "python-pg.py"
  "UDP_Server.py"
  "player_entry.py"
  "play_action.py"
  "splashscreen.py"
)

for file in "${required_files[@]}"; do
  if [ ! -f "$file" ]; then
    echo "ERROR: Missing required file: $file"
    exit 1
  fi
done

# 6) Launch UDP server in background
echo "Starting UDP server..."
python UDP_Server.py &
SERVER_PID=$!

# Clean up background server on exit
cleanup() {
  echo ""
  echo "Stopping UDP server..."
  kill "$SERVER_PID" 2>/dev/null || true
}
trap cleanup EXIT

# 7) Launch Photon app
echo "Starting Photon app..."
python python-pg.py
