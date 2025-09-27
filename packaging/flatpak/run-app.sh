#!/usr/bin/env bash
set -euo pipefail

# Fall back to ~/.cache if XDG_CACHE_HOME is not set
export RECTIFEX_CACHE_DIR="${XDG_CACHE_HOME:-$HOME/.cache}/com.rectifex.GlobalScreener"

# Optional: silence host LD_PRELOAD warnings
unset LD_PRELOAD || true

exec python3 -m app "$@"
