"""Shared pytest fixtures and markers for videoflow-align.

Integration tests spawn the real MCP server as a subprocess and are
gated by ``--run-integration`` (mirrors the top-level repo convention).
They also require ``faster-whisper`` to be importable — if the model
weights aren't cached locally the first run will download ~150 MB.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser):
    # When run from the repo root, tests/conftest.py already registered this
    # option — don't re-register or pytest raises ValueError on collection.
    existing = {opt.dest for opt in parser._anonymous.options}
    if "run_integration" in existing:
        return
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run MCP integration tests that spawn the videoflow-align server.",
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-integration"):
        return
    skip = pytest.mark.skip(
        reason="MCP integration tests need --run-integration (spawns real server, "
        "may download faster-whisper model)."
    )
    for item in items:
        if "mcp_integration" in item.keywords:
            item.add_marker(skip)
