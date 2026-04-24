#!/usr/bin/env bash
#
# run_tests.sh - Run pytest tests using the venv
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_PYTHON="$SCRIPT_DIR/python_scripts/venv/bin/python3"
PYTEST="$SCRIPT_DIR/python_scripts/venv/bin/pytest"

# Check if venv exists
if [ ! -f "$VENV_PYTHON" ]; then
    echo "Error: Virtual environment not found." >&2
    echo "Please run: python_scripts/setup_venv.sh" >&2
    exit 1
fi

# Check if pytest is installed
if [ ! -f "$PYTEST" ]; then
    echo "Error: pytest not found." >&2
    echo "Installing pytest..." >&2
    "$VENV_PYTHON" -m pip install pytest pytest-cov
fi

# Run pytest with coverage
echo "Running tests..."
echo ""

cd "$SCRIPT_DIR"
"$PYTEST" tests/ -v --cov=python_scripts --cov-report=term-missing "$@"

echo ""
echo "Tests complete!"
