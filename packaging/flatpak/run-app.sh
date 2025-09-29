#!/usr/bin/env bash
set -euo pipefail

# Add the application source directory to Python's path
export PYTHONPATH=/app/src

# Execute the main application module
exec python3 -m app "$@"