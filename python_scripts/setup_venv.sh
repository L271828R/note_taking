#!/usr/bin/env bash
#
# setup_venv.sh - Setup Python virtual environment for note scripts
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$SCRIPT_DIR/venv"

echo "Setting up Python virtual environment..."
echo "Location: $VENV_DIR"

# Create venv if it doesn't exist
if [ ! -d "$VENV_DIR" ]; then
    echo "Creating new virtual environment..."
    python3 -m venv "$VENV_DIR"
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate and upgrade pip
echo "Upgrading pip..."
"$VENV_DIR/bin/pip" install --upgrade pip > /dev/null 2>&1

# Install any requirements if requirements.txt exists
if [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    echo "Installing requirements..."
    "$VENV_DIR/bin/pip" install -r "$SCRIPT_DIR/requirements.txt"
fi

echo ""
echo "✓ Setup complete!"
echo ""
echo "Virtual environment ready at: $VENV_DIR"
echo "Python binary: $VENV_DIR/bin/python3"
echo ""
