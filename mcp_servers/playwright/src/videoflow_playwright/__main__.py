"""MCP Server entry point for videoflow-playwright.

Usage:
    videoflow-playwright                     # stdio transport (default)
    videoflow-playwright --headless false   # Show browser window
    videoflow-playwright --browser-channel chrome  # Use installed Chrome

For Claude Code MCP integration, add to ~/.claude/mcp.json:
    {
        "mcpServers": {
            "videoflow-playwright": {
                "command": "videoflow-playwright"
            }
        }
    }
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Any

from .recorder import BrowserRecorder, RecordingOptions, Viewport

_LOGGER = logging.getLogger(__name__)
_SERVER_INFO = {
    "name": "videoflow-playwright",
    "version": "0.1.0.dev0",
}


def _parse_args() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="videoflow-playwright MCP Server — screen capture to video",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--headless",
        type=lambda x: x.lower() in ("true", "1", "yes"),
        default=True,
        help="Run browser in headless mode (default: true)",
    )
    parser.add_argument(
        "--browser-channel",
        default="chromium",
        choices=["chromium", "chrome", "msedge"],
        help="Browser channel to use (default: chromium)",
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
    recorder: BrowserRecorder | None = None

    @server.list_tools()
    async def handle_list_tools() -> list[dict[str, Any]]:
        """List available tools."""
        return [
            {
                "name": "capture_url",
                "description": "Capture a URL as MP4 video using Playwright + ffmpeg.",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to capture.",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output MP4 file path.",
                        },
                        "duration": {
                            "type": "number",
                            "description": "Recording duration in seconds (default: 5).",
                        },
                        "viewport_width": {
                            "type": "integer",
                            "description": "Browser viewport width (default: 1920).",
                        },
                        "viewport_height": {
                            "type": "integer",
                            "description": "Browser viewport height (default: 1080).",
                        },
                        "fps": {
                            "type": "integer",
                            "description": "Frame rate (default: 30).",
                        },
                        "quality": {
                            "type": "string",
                            "enum": ["low", "medium", "high"],
                            "description": "Video quality (default: high).",
                        },
                    },
                    "required": ["url", "output_path"],
                },
            },
            {
                "name": "capture_url_with_interactions",
                "description": "Capture a URL with interaction scripts (clicks, scrolls, typing).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string",
                            "description": "URL to capture.",
                        },
                        "output_path": {
                            "type": "string",
                            "description": "Output MP4 file path.",
                        },
                        "duration": {
                            "type": "number",
                            "description": "Recording duration in seconds (default: 5).",
                        },
                        "viewport_width": {
                            "type": "integer",
                            "description": "Browser viewport width (default: 1920).",
                        },
                        "viewport_height": {
                            "type": "integer",
                            "description": "Browser viewport height (default: 1080).",
                        },
                        "clicks": {
                            "type": "array",
                            "description": "Click actions: [{selector: CSS selector}, ...]",
                            "items": {"type": "object"},
                        },
                        "scrolls": {
                            "type": "array",
                            "description": "Scroll actions: [{selector: CSS selector, x: number, y: number}, ...]",
                            "items": {"type": "object"},
                        },
                        "type_texts": {
                            "type": "array",
                            "description": "Type actions: [{selector: CSS selector, text: string}, ...]",
                            "items": {"type": "object"},
                        },
                        "wait_for_selectors": {
                            "type": "array",
                            "description": "Selectors to wait for before recording: [selector, ...]",
                            "items": {"type": "string"},
                        },
                    },
                    "required": ["url", "output_path"],
                },
            },
            {
                "name": "check_browser",
                "description": "Check if Playwright Chromium is available.",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]

    @server.call_tool()
    async def handle_call_tool(
        name: str,
        arguments: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Execute a tool."""
        return await _handle_tool(name, arguments, recorder)

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


async def _handle_tool(
    name: str,
    arguments: dict[str, Any],
    recorder: BrowserRecorder | None,
) -> list[dict[str, Any]]:
    """Handle tool calls."""
    global _server_recorder

    if name == "check_browser":
        return await _handle_check_browser()

    elif name == "capture_url":
        return await _handle_capture_url(arguments)

    elif name == "capture_url_with_interactions":
        return await _handle_capture_url_with_interactions(arguments)

    else:
        raise ValueError(f"Unknown tool: {name}")


async def _handle_check_browser() -> list[dict[str, Any]]:
    """Check browser availability."""
    checks = []

    # Check Playwright
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            version = browser.version
            browser.close()
        checks.append(("playwright", True, version))
    except Exception as e:
        checks.append(("playwright", False, str(e)))

    # Check ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        checks.append(("ffmpeg", True, ffmpeg_path))
    else:
        checks.append(("ffmpeg", False, "not found"))

    # Check Chromium
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        checks.append(("chromium", True, "available"))
    except Exception as e:
        checks.append(("chromium", False, str(e)))

    all_ok = all(check[1] for check in checks)
    summary = "\n".join(
        f"- {check[0]}: {'✓' if check[1] else '✗'} {check[2]}"
        for check in checks
    )

    return [
        {
            "type": "text",
            "text": f"Browser check: {'OK' if all_ok else 'ISSUES DETECTED'}\n{summary}",
        }
    ]


async def _handle_capture_url(arguments: dict[str, Any]) -> list[dict[str, Any]]:
    """Handle capture_url tool."""
    url = arguments["url"]
    output_path = Path(arguments["output_path"])
    duration = arguments.get("duration", 5.0)
    viewport_width = arguments.get("viewport_width", 1920)
    viewport_height = arguments.get("viewport_height", 1080)
    fps = arguments.get("fps", 30)
    quality = arguments.get("quality", "high")

    _LOGGER.info(
        "capture_url: url=%s, output=%s, duration=%.1f",
        url,
        output_path,
        duration,
    )

    try:
        result = await record_screen(
            url=url,
            output_path=output_path,
            duration=duration,
            viewport_width=viewport_width,
            viewport_height=viewport_height,
            fps=fps,
            quality=quality,
        )

        return [
            {
                "type": "text",
                "text": (
                    f"Recording complete!\n"
                    f"Output: {result.output_path}\n"
                    f"Duration: {result.duration:.2f}s\n"
                    f"Resolution: {result.width}x{result.height}\n"
                    f"Size: {BrowserRecorder._format_size(result.file_size)}"
                ),
            }
        ]

    except Exception as e:
        _LOGGER.exception("Recording failed")
        raise RuntimeError(f"Recording failed: {e}") from e


async def _handle_capture_url_with_interactions(
    arguments: dict[str, Any],
) -> list[dict[str, Any]]:
    """Handle capture_url_with_interactions tool."""
    url = arguments["url"]
    output_path = Path(arguments["output_path"])
    duration = arguments.get("duration", 5.0)
    viewport_width = arguments.get("viewport_width", 1920)
    viewport_height = arguments.get("viewport_height", 1080)
    clicks = arguments.get("clicks", [])
    scrolls = arguments.get("scrolls", [])
    type_texts = arguments.get("type_texts", [])
    wait_for_selectors = arguments.get("wait_for_selectors", [])

    _LOGGER.info(
        "capture_url_with_interactions: url=%s, output=%s, duration=%.1f, interactions=%d",
        url,
        output_path,
        duration,
        len(clicks) + len(scrolls) + len(type_texts),
    )

    try:
        recorder = await BrowserRecorder.get_instance()

        options = RecordingOptions(
            url=url,
            output_path=output_path,
            duration=duration,
            viewport=Viewport(width=viewport_width, height=viewport_height),
            clicks=clicks,
            scrolls=scrolls,
            type_texts=type_texts,
            wait_for_selectors=wait_for_selectors,
        )

        result = await recorder.record(options)

        return [
            {
                "type": "text",
                "text": (
                    f"Recording with interactions complete!\n"
                    f"Output: {result.output_path}\n"
                    f"Duration: {result.duration:.2f}s\n"
                    f"Resolution: {result.width}x{result.height}\n"
                    f"Size: {BrowserRecorder._format_size(result.file_size)}"
                ),
            }
        ]

    except Exception as e:
        _LOGGER.exception("Recording with interactions failed")
        raise RuntimeError(f"Recording failed: {e}") from e


# Global recorder instance for reuse
_server_recorder: BrowserRecorder | None = None


async def main() -> None:
    """Run the MCP server."""
    global _server_recorder

    args = _parse_args()

    # Set up logging
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    _LOGGER.info(
        "Starting videoflow-playwright v%s (headless=%s, channel=%s)",
        _SERVER_INFO["version"],
        args.headless,
        args.browser_channel,
    )

    try:
        # Pre-warm the browser
        _server_recorder = await BrowserRecorder.get_instance(
            headless=args.headless,
            browser_channel=args.browser_channel,
        )
        _LOGGER.info("Browser instance warmed up and ready")

        await _run_stdio()
    except KeyboardInterrupt:
        _LOGGER.info("Shutting down...")
    except Exception as e:
        _LOGGER.exception("Server error")
        raise
    finally:
        if _server_recorder:
            await _server_recorder.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        _LOGGER.info("Shutting down.")
        sys.exit(0)
    except Exception as e:
        _LOGGER.exception("Fatal error")
        sys.exit(1)
