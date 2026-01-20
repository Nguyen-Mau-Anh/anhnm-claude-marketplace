#!/bin/bash
# Orchestrator runner - self-locating script

# Get the directory where this script is located
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Install dependencies if needed
pip install -q -r "${SCRIPT_DIR}/requirements.txt" 2>/dev/null || pip install -q rich typer pydantic pyyaml aiofiles

# Run the orchestrator with correct PYTHONPATH
PYTHONPATH="${SCRIPT_DIR}" python3 -m orchestrator "$@"
