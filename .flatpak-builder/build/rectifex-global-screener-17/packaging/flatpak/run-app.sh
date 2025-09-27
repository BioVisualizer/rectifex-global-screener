#!/usr/bin/env bash
set -euo pipefail
cd /app/rectifex-global-screener
exec /usr/bin/python3 -m app  # passe auf Wunsch an (z.B. -m app.main oder python3 app/main.py)
