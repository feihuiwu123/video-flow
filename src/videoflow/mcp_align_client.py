"""MCP client for the videoflow-align server.

This module provides a thin wrapper around the align_subtitle MCP tool,
allowing videoflow to optionally use word-level subtitle alignment.

The align server must be running (via stdio transport) or accessible via SSE.
Set ALIGN_MCP_TRANSPORT env var to "sse" for localhost access.

Example:
    from videoflow.mcp_align_client import AlignMCPClient

    client = AlignMCPClient()
    segments = await client.align_subtitle(
        audio_path="/path/to/audio.mp3",
        text="The narration text",
        output_ass="/path/to/output.ass",
    )
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

from videoflow.config import AlignConfig

_LOGGER = logging.getLogger(__name__)

# MCP protocol version
MCP_PROTOCOL_VERSION = "2024-11-05"


@dataclass
class WordTiming:
    """One word with start/end seconds and probability."""

    word: str
    start: float
    end: float
    probability: float = 1.0


@dataclass
class Segment:
    """A sentence-level segment containing one or more words."""

    start: float
    end: float
    text: str
    words: list[WordTiming] = field(default_factory=list)


@dataclass
class AlignmentResult:
    """Result from the align_subtitle tool."""

    segments: list[Segment]
    detected_language: str
    duration: float
    num_segments: int
    num_words: int


class AlignMCPError(Exception):
    """Raised when the align MCP call fails."""

    pass


class AlignMCPUnavailable(Exception):
    """Raised when the align MCP server is not available."""

    pass


class AlignMCPClient:
    """Client for the videoflow-align MCP server.

    Supports stdio transport (spawns server as subprocess) or
    SSE transport (connects to running server at localhost:8765).
    """

    def __init__(
        self,
        config: Optional[AlignConfig] = None,
        timeout: float = 120.0,
    ) -> None:
        """Initialize the align MCP client.

        Args:
            config: Align configuration. If None, uses defaults.
            timeout: Maximum time to wait for alignment in seconds.
        """
        self.config = config or AlignConfig()
        self.timeout = timeout

        # Check if the server command is available
        self._server_cmd = self._find_server_command()

    def _find_server_command(self) -> Optional[str]:
        """Find the videoflow-align executable."""
        # Check if it's installed as a console script
        if shutil.which("videoflow-align"):
            return "videoflow-align"

        # Check if we can import the module directly
        try:
            import videoflow_align  # noqa: F401
            return f"{sys.executable} -m videoflow_align"
        except ImportError:
            pass

        return None

    def is_available(self) -> bool:
        """Check if the align MCP server is available."""
        return self._server_cmd is not None

    async def align_subtitle(
        self,
        audio_path: Path,
        text: str,
        output_ass: Path,
        language: str = "auto",
        model_size: Optional[str] = None,
        word_timestamps: bool = True,
    ) -> AlignmentResult:
        """Align subtitles using the MCP server.

        Args:
            audio_path: Path to the audio file (MP3/WAV).
            text: Expected transcript text.
            output_ass: Where to write the ASS file.
            language: ISO code or "auto" for detection.
            model_size: Override the model size (default: from config).
            word_timestamps: Enable word-level karaoke timing.

        Returns:
            AlignmentResult with segments and metadata.

        Raises:
            AlignMCPUnavailable: If the server is not available.
            AlignMCPError: If the alignment fails.
        """
        if not self.is_available():
            raise AlignMCPUnavailable(
                "videoflow-align not found. "
                "Install with: pip install -e ./mcp_servers/align[dev]"
            )

        if not audio_path.exists():
            raise FileNotFoundError(f"Audio file not found: {audio_path}")

        # Use config defaults
        model_size = model_size or self.config.model_size
        language = language or self.config.language

        _LOGGER.info(
            "Starting align MCP: audio=%s, lang=%s, model=%s",
            audio_path,
            language,
            model_size,
        )

        try:
            if self.config.mcp_transport == "sse":
                result = await self._call_via_sse(
                    audio_path, text, output_ass, language, model_size, word_timestamps
                )
            else:
                result = await self._call_via_stdio(
                    audio_path, text, output_ass, language, model_size, word_timestamps
                )

            _LOGGER.info(
                "Alignment complete: %d segments, %d words, %.2fs",
                result.num_segments,
                result.num_words,
                result.duration,
            )
            return result

        except Exception as e:
            _LOGGER.exception("Alignment failed")
            raise AlignMCPError(f"Alignment failed: {e}") from e

    async def _call_via_stdio(
        self,
        audio_path: Path,
        text: str,
        output_ass: Path,
        language: str,
        model_size: str,
        word_timestamps: bool,
    ) -> AlignmentResult:
        """Call the align MCP server via stdio transport (spawn subprocess)."""
        # Build the server command
        cmd = self._server_cmd.split() if " " not in self._server_cmd else self._server_cmd.split()

        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            # Initialize
            init_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": MCP_PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": {"name": "videoflow", "version": "0.1.0"},
                },
            }
            proc.stdin.write((json.dumps(init_request) + "\n").encode())
            await proc.stdin.drain()

            # Read init response
            response = await asyncio.wait_for(proc.stdout.readline(), timeout=30.0)
            init_result = json.loads(response.decode())
            if "error" in init_result:
                raise AlignMCPError(f"Initialize failed: {init_result['error']}")

            # Call align_subtitle tool
            call_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": "align_subtitle",
                    "arguments": {
                        "audio_path": str(audio_path),
                        "text": text,
                        "output_ass": str(output_ass),
                        "language": language,
                        "model_size": model_size,
                        "word_timestamps": word_timestamps,
                    },
                },
            }
            proc.stdin.write((json.dumps(call_request) + "\n").encode())
            await proc.stdin.drain()

            # Read response with timeout (model download + transcription can take time)
            response = await asyncio.wait_for(proc.stdout.readline(), timeout=self.timeout)
            call_result = json.loads(response.decode())

            if "error" in call_result:
                raise AlignMCPError(f"Tool call failed: {call_result['error']}")

            # Parse the response text to extract metadata
            text_content = call_result.get("result", {}).get("content", [])
            summary_text = ""
            for content in text_content:
                if content.get("type") == "text":
                    summary_text = content.get("text", "")
                    break

            # Extract metadata from summary
            detected_lang = self._extract_field(summary_text, "Detected language")
            duration = float(self._extract_field(summary_text, "Duration") or "0")
            num_segments = int(self._extract_field(summary_text, "Segments") or "0")
            num_words = int(self._extract_field(summary_text, "Words") or "0")

            return AlignmentResult(
                segments=[],  # Caller can read from output_ass if needed
                detected_language=detected_lang,
                duration=duration,
                num_segments=num_segments,
                num_words=num_words,
            )

        finally:
            # Clean shutdown
            try:
                proc.terminate()
                await asyncio.wait_for(proc.wait(), timeout=3.0)
            except asyncio.TimeoutError:
                proc.kill()
                await proc.wait()

    async def _call_via_sse(
        self,
        audio_path: Path,
        text: str,
        output_ass: Path,
        language: str,
        model_size: str,
        word_timestamps: bool,
    ) -> AlignmentResult:
        """Call the align MCP server via SSE transport (requires running server)."""
        import aiohttp

        # SSE endpoint default
        base_url = os.environ.get("ALIGN_MCP_URL", "http://localhost:8765")

        async with aiohttp.ClientSession() as session:
            # Note: SSE transport requires a different RPC approach
            # For now, fall back to stdio if SSE is needed
            # TODO: Implement full SSE/HTTP MCP client
            raise AlignMCPError(
                "SSE transport not yet implemented. "
                "Use stdio transport or set ALIGN_MCP_TRANSPORT=stdio"
            )

    @staticmethod
    def _extract_field(text: str, field_name: str) -> Optional[str]:
        """Extract a field value from summary text."""
        for line in text.split("\n"):
            if line.startswith(f"{field_name}:"):
                return line.split(":", 1)[1].strip()
        return None


def align_via_mcp(
    audio_path: Path,
    text: str,
    output_ass: Path,
    config: Optional[AlignConfig] = None,
) -> AlignmentResult:
    """Synchronous wrapper for async alignment.

    Args:
        audio_path: Path to audio file.
        text: Expected transcript.
        output_ass: Output ASS path.
        config: Optional configuration.

    Returns:
        AlignmentResult.

    Raises:
        AlignMCPUnavailable: If MCP server unavailable.
        AlignMCPError: If alignment fails.
    """
    client = AlignMCPClient(config=config)
    return asyncio.run(
        client.align_subtitle(audio_path, text, output_ass)
    )


def is_align_mcp_available() -> bool:
    """Check if the align MCP is available without raising."""
    try:
        client = AlignMCPClient()
        return client.is_available()
    except Exception:
        return False
