"""Test helper configuration for the Rectifex project."""

from __future__ import annotations

import os

# Prevent third-party pytest plugins from auto-loading in environments lacking GUI deps.
os.environ.setdefault("PYTEST_DISABLE_PLUGIN_AUTOLOAD", "1")
