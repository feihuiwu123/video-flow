"""MCP Server entry point for videoflow-align.

Usage:
    videoflow-align                      # stdio transport (default)
    videoflow-align --transport sse       # SSE on localhost:8765

For Claude Code MCP integration, add to ~/.claude/mcp.json:
    {
        "mcpServers": {
            "videoflow-align": {
                "command": "videoflow-align"
            }
        }
    }
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import sys
from pathlib import Path
from typing import Any

from .ass_writer import AssStyle, write_ass
from .engine import align_audio_with_text

_LOGGER = logging.getLogger(__name__)
_SERVER_INFO = {
    "name": "videoflow-align",
    "version": "0.1.0.dev0",
}


class AlignSubtitleArguments:
    """Parameters for the align_subtitle tool."""

    def __init__(
        self,
        audio_path: str,
        text: str,
        output_ass: str,
        language: str = "auto",
        model_size: str = "base",
        word_timestamps: bool = True,
    ) -> None:
        self.audio_path = audio_path
        self.text = text
        self.output_ass = output_ass
        self.language = language
        self.model_size = model_size
        self.word_timestamps = word_timestamps


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="videoflow-align MCP Server — word-level subtitle alignment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--transport",
        choices=["stdio", "sse"],
        default="stdio",
        help="MCP transport: stdio (default) or sse (localhost:8765)",
    )
    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="SSE server host (default: 0.0.0.0)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8765,
        help="SSE server port (default: 8765)",
    )
    parser.add_argument(
        "--log-level",
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Log level (default: INFO)",
    )
    return parser.parse_args()


async def _run_stdio() -> None:
    """Run the MCP server over stdio transport."""
    import mcp.server.stdio
    from mcp.server import Server
    from mcp.server.models import InitializationOptions

    server = Server(_SERVER_INFO["name"], _SERVER_INFO["version"])

    @server.list_tools()
    async def handle_list_tools() -> list[dict[str, Any]]:
        """List available tools."""
        return [
            {
                "name": "align_subtitle",
                "description": "Generate word-level timed ASS subtitles from audio + text.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "audio_path": {"type": "string", "description": "Absolute path to MP3 / WAV."},
                        "text": {"type": "string", "description": "Expected transcript; used as initial prompt + fallback."},
                        "output_ass": {"type": "string", "description": "Where to write the ASS file."},
                        "language": {"type": "string", "description": "ISO code (e.g. 'zh', 'en') or 'auto' for detection."},
                        "model_size": {"type": "string", "description": "Any faster-whisper size: tiny / base / small / ..."},
                        "word_timestamps": {"type": "boolean", "description": "Emit one ASS event per word with {\\k} karaoke tags."},
                    },
                    "required": ["audio_path", "text", "output_ass"],
                },
            }
        ]

    @server.call_tool()
    async def handle_call_tool(name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
        """Execute a tool."""
        return await _handle_align_tool(name, arguments)

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name=_SERVER_INFO["name"],
                server_version=_SERVER_INFO["version"],
                capabilities=server.get_capabilities(),
            ),
        )


async def _handle_align_tool(name: str, arguments: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle the align_subtitle tool call."""
    if name != "align_subtitle":
        raise ValueError(f"Unknown tool: {name}")

    # Validate input
    try:
        args = AlignSubtitleArguments(**arguments)
    except Exception as e:
        raise ValueError(f"Invalid arguments: {e}") from e

    _LOGGER.info(
        "align_subtitle: audio=%s, text=%d chars, language=%s, model=%s",
        args.audio_path,
        len(args.text),
        args.language,
        args.model_size,
    )

    audio_path = Path(args.audio_path)
    output_path = Path(args.output_ass)

    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Run alignment
    try:
        segments, detected_language = align_audio_with_text(
            audio_path=audio_path,
            text=args.text,
            language=args.language,
            model_size=args.model_size,
            word_timestamps=args.word_timestamps,
        )
    except Exception as e:
        _LOGGER.exception("Alignment failed")
        raise RuntimeError(f"Alignment failed: {e}") from e

    # Write ASS file
    try:
        write_ass(
            segments=segments,
            output_path=output_path,
            style=AssStyle(),
        )
    except Exception as e:
        _LOGGER.exception("ASS writing failed")
        raise RuntimeError(f"ASS writing failed: {e}") from e

    # Compute summary stats
    total_words = sum(len(seg.words) for seg in segments)
    duration = max((seg.end for seg in segments), default=0.0)

    _LOGGER.info(
        "Alignment complete: %d segments, %d words, duration=%.2fs, language=%s",
        len(segments),
        total_words,
        duration,
        detected_language,
    )

    ass_content = output_path.read_text(encoding="utf-8")
    preview = ass_content[:5000] + ("..." if len(ass_content) > 5000 else "")

    return [
        {
            "type": "text",
            "text": (
                f"Generated word-level ASS subtitles at {output_path}\n"
                f"Detected language: {detected_language}\n"
                f"Duration: {duration:.2f} s\n"
                f"Segments: {len(segments)}\n"
                f"Words: {total_words}"
            ),
        },
        {
            "type": "resource",
            "resource": {
                "uri": f"file://{output_path.resolve()}",
                "mimeType": "text/x-ass",
                "text": preview,
            },
        },
    ]


async def main() -> None:
    """Run the MCP server."""
    args = _parse_args()

    # Set up logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    _LOGGER.info(
        "Starting videoflow-align v%s (transport=%s)",
        _SERVER_INFO["version"],
        args.transport,
    )

    if args.transport == "sse":
        _LOGGER.warning("SSE transport is not yet fully implemented — falling back to stdio")
        await _run_stdio()
    else:
        await _run_stdio()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _LOGGER.info("Shutting down.")
        sys.exit(0)
    except Exception as e:
        _LOGGER.exception("Fatal error")
        sys.exit(1)
