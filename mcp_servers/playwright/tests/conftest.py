"""Pytest configuration for videoflow-playwright tests."""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the package can be imported when running from the repo
src_path = Path(__file__).parent.parent / "src"
if str(src_path) not in sys.path:
    sys.path.insert(0, str(src_path))
