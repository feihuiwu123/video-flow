"""Mermaid CLI wrapper for generating SVG diagrams.

This module provides a thin wrapper around the Mermaid CLI (or Node.js API)
to generate SVG diagrams from Mermaid syntax. The SVG can then be embedded
in Remotion compositions or rendered as static images.

Install Mermaid CLI:
    npm install -g @mermaid-js/mermaid-cli
    # or
    brew install mermaid-cli

Usage:
    from videoflow.mermaid import render_mermaid

    svg = render_mermaid("graph TD; A --> B")
    svg_path.write_text(svg)
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_LOGGER = logging.getLogger(__name__)


@dataclass
class MermaidConfig:
    """Configuration for Mermaid rendering."""

    width: int = 1080
    height: int = 1920
    background_color: str = "#0A1929"
    theme: str = "dark"  # dark, light, neutral
    font_family: str = "Noto Sans SC, sans-serif"
    font_size: int = 24


def _find_mermaid_cli() -> Optional[str]:
    """Find the mermaid CLI executable."""
    # Check common locations
    candidates = [
        "mmdc",  # npm global
        "mermaid",
        Path.home() / ".npm-global" / "bin" / "mmdc",
        Path.home() / ".nvm" / "versions" / "node" / "v18" / "bin" / "mmdc",
    ]

    for candidate in candidates:
        if isinstance(candidate, str) and shutil.which(candidate):
            return candidate
        elif isinstance(candidate, Path) and candidate.exists():
            return str(candidate)

    return None


def is_mermaid_available() -> bool:
    """Check if Mermaid CLI is available."""
    return _find_mermaid_cli() is not None


def render_mermaid(
    mermaid_code: str,
    output_path: Optional[Path] = None,
    config: Optional[MermaidConfig] = None,
) -> Path:
    """Render Mermaid diagram to SVG.

    Args:
        mermaid_code: Mermaid syntax string.
        output_path: Output SVG path (auto-generated if None).
        config: Rendering configuration.

    Returns:
        Path to the generated SVG file.

    Raises:
        RuntimeError: If Mermaid CLI is not available or rendering fails.
    """
    mmdc = _find_mermaid_cli()
    if not mmdc:
        raise RuntimeError(
            "Mermaid CLI not found. Install with:\n"
            "  npm install -g @mermaid-js/mermaid-cli\n"
            "  # or\n"
            "  brew install mermaid-cli"
        )

    cfg = config or MermaidConfig()

    # Create temp file for input
    if output_path is None:
        output_path = Path(tempfile.mktemp(suffix=".svg"))

    input_file = Path(tempfile.mktemp(suffix=".mmd"))
    input_file.write_text(mermaid_code, encoding="utf-8")

    # Build command
    cmd = [
        mmdc,
        "-i", str(input_file),
        "-o", str(output_path),
        "-w", str(cfg.width),
        "-H", str(cfg.height),
        "-b", cfg.background_color,
        "-t", cfg.theme,
        "-F", str(cfg.font_size),
    ]

    _LOGGER.debug("Running mermaid: %s", " ".join(cmd))

    try:
        result = subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
        _LOGGER.debug("Mermaid output: %s", result.stdout)

        # Clean up input
        input_file.unlink(missing_ok=True)

        if not output_path.exists():
            raise RuntimeError(f"Mermaid CLI succeeded but no output at {output_path}")

        return output_path

    except subprocess.CalledProcessError as e:
        _LOGGER.error("Mermaid CLI failed: %s", e.stderr)
        raise RuntimeError(f"Mermaid rendering failed: {e.stderr}") from e


def render_mermaid_to_base64(
    mermaid_code: str,
    config: Optional[MermaidConfig] = None,
) -> str:
    """Render Mermaid diagram to base64-encoded SVG.

    Useful for embedding in HTML or data URIs.

    Args:
        mermaid_code: Mermaid syntax string.
        config: Rendering configuration.

    Returns:
        Base64-encoded SVG string.
    """
    import base64

    with tempfile.NamedTemporaryFile(suffix=".svg", delete=False) as f:
        output_path = Path(f.name)

    try:
        render_mermaid(mermaid_code, output_path, config)
        svg_content = output_path.read_text(encoding="utf-8")
        return base64.b64encode(svg_content.encode("utf-8")).decode("ascii")
    finally:
        output_path.unlink(missing_ok=True)


# Example Mermaid templates
MERMAID_TEMPLATES = {
    "flowchart_basic": """flowchart TD
    A[Start] --> B{Decision}
    B -->|Yes| C[Action 1]
    B -->|No| D[Action 2]
    C --> E[End]
    D --> E""",

    "flowchart_process": """flowchart LR
    A[Input] --> B[Process 1]
    B --> C[Process 2]
    C --> D{Success?}
    D -->|Yes| E[Output]
    D -->|No| F[Error Handler]
    F --> B""",

    "sequence_api": """sequenceDiagram
    participant C as Client
    participant S as Server
    participant D as Database
    C->>S: Request
    S->>D: Query
    D-->>S: Result
    S-->>C: Response""",

    "pie_chart": """pie title Distribution
    "Category A" : 40
    "Category B" : 35
    "Category C" : 25""",

    "timeline": """gantt
    title Project Timeline
    dateFormat YYYY-MM-DD
    section Phase 1
    Task 1 :2024-01-01, 30d
    Task 2 :2024-01-15, 20d
    section Phase 2
    Task 3 :2024-02-01, 25d
    Task 4 :2024-02-20, 15d""",
}
