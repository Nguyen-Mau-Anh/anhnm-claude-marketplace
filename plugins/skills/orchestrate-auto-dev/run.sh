#!/usr/bin/env bash
# Auto-detect Python executable and run orchestrate-auto-dev
# This script ensures compatibility whether 'python' or 'python3' is available

set -e

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Detect available Python executable
PYTHON_CMD=""

if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "Error: Neither 'python' nor 'python3' found in PATH"
    echo "Please install Python 3.8 or later"
    exit 127
fi

# Run the executor module with all arguments passed through
cd "$SCRIPT_DIR"
exec "$PYTHON_CMD" -m executor "$@"
