#!/bin/sh
export PYTHONPATH="${PYTHONPATH:+$PYTHONPATH:}/app/rectifex-global-screener"
exec python3 -m app "$@"
