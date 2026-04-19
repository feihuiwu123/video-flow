"""videoflow-playwright — MCP Server for screen capture to video."""

__version__ = "0.1.0.dev0"

from .recorder import BrowserRecorder, RecordingOptions, RecordingResult

__all__ = [
    "BrowserRecorder",
    "RecordingOptions",
    "RecordingResult",
]
