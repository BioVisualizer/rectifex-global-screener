#!/usr/bin/env bash
set -euo pipefail

# Add the application source directory to Python's path
export PYTHONPATH=/app/src

# Execute the main CLI module
exec python3 -m cli.rectifex_cli "$@"