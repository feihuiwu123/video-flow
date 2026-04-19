"""Integration tests for the Playwright MCP server.

These tests require playwright installed with chromium.
Run with: pytest tests/ -v -m pw_integration

Usage:
    # From mcp_servers/playwright/
    playwright install chromium
    pytest tests/ -v -m pw_integration

    # Or from repo root
    pytest mcp_servers/playwright/tests/ -v -m pw_integration
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

from videoflow_playwright import __version__

MCP_PROTOCOL_VERSION = "2024-11-05"


def check_prerequisites() -> tuple[bool, str]:
    """Check if prerequisites are met."""
    # Check playwright
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            browser.close()
        playwright_ok = True
    except Exception as e:
        playwright_ok = False
        playwright_err = str(e)

    # Check ffmpeg
    ffmpeg_ok = shutil.which("ffmpeg") is not None

    return playwright_ok and ffmpeg_ok, f"playwright={playwright_ok}, ffmpeg={ffmpeg_ok}"


@pytest.fixture(scope="module")
def prerequisites_met():
    """Skip tests if prerequisites not met."""
    ok, status = check_prerequisites()
    if not ok:
        pytest.skip(f"Prerequisites not met: {status}")
    return True


@pytest.fixture
def temp_output():
    """Create a temporary output file."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir) / "output.mp4"


async def _spawn_server() -> tuple[asyncio.subprocess.Process, Path]:
    """Spawn the MCP server as a subprocess."""
    tmpdir = Path(tempfile.mkdtemp())
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "videoflow_playwright",
        "--headless",
        "true",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    return proc, tmpdir


async def _init_server(proc: asyncio.subprocess.Process) -> dict:
    """Initialize the MCP server."""
    init_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": MCP_PROTOCOL_VERSION,
            "capabilities": {},
            "clientInfo": {"name": "integration-test", "version": "0.1.0"},
        },
    }
    proc.stdin.write((json.dumps(init_request) + "\n").encode())
    await proc.stdin.drain()
    line = await proc.stdout.readline()
    return json.loads(line.decode())


async def _list_tools(proc: asyncio.subprocess.Process) -> list[dict]:
    """List available tools."""
    tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
    }
    proc.stdin.write((json.dumps(tools_request) + "\n").encode())
    await proc.stdin.drain()
    line = await proc.stdout.readline()
    response = json.loads(line.decode())
    return response["result"]["tools"]


async def _call_tool(proc: asyncio.subprocess.Process, name: str, arguments: dict) -> dict:
    """Call a tool."""
    call_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": name,
            "arguments": arguments,
        },
    }
    proc.stdin.write((json.dumps(call_request) + "\n").encode())
    await proc.stdin.drain()
    line = await proc.stdout.readline()
    return json.loads(line.decode())


@pytest.mark.pw_integration
@pytest.mark.asyncio
async def test_server_initialization(prerequisites_met):
    """Test that the server starts and initializes correctly."""
    proc, tmpdir = await _spawn_server()
    try:
        result = await _init_server(proc)

        assert "result" in result
        assert result["result"]["serverInfo"]["name"] == "videoflow-playwright"
        assert result["result"]["serverInfo"]["version"] == __version__

    finally:
        proc.terminate()
        await proc.wait()


@pytest.mark.pw_integration
@pytest.mark.asyncio
async def test_tools_registered(prerequisites_met):
    """Test that all tools are registered."""
    proc, tmpdir = await _spawn_server()
    try:
        await _init_server(proc)
        tools = await _list_tools(proc)

        tool_names = [t["name"] for t in tools]
        assert "capture_url" in tool_names
        assert "capture_url_with_interactions" in tool_names
        assert "check_browser" in tool_names

    finally:
        proc.terminate()
        await proc.wait()


@pytest.mark.pw_integration
@pytest.mark.asyncio
async def test_check_browser(prerequisites_met):
    """Test the check_browser tool."""
    proc, tmpdir = await _spawn_server()
    try:
        await _init_server(proc)
        result = await _call_tool(proc, "check_browser", {})

        assert "result" in result
        content = result["result"]["content"]
        text = content[0]["text"]
        assert "playwright" in text.lower()
        assert "ffmpeg" in text.lower()

    finally:
        proc.terminate()
        await proc.wait()


@pytest.mark.pw_integration
@pytest.mark.asyncio
async def test_capture_url_simple(prerequisites_met, temp_output):
    """Test basic URL capture."""
    proc, tmpdir = await _spawn_server()
    try:
        await _init_server(proc)

        result = await _call_tool(
            proc,
            "capture_url",
            {
                "url": "https://example.com",
                "output_path": str(temp_output),
                "duration": 2.0,  # Short duration for testing
            },
        )

        assert "result" in result
        # Note: This may fail if example.com blocks automated access
        # In that case, we check the error message
        if "error" in result:
            pytest.skip(f"Recording failed (likely blocked): {result['error']}")

        # Check output file
        if temp_output.exists():
            assert temp_output.stat().st_size > 0

    finally:
        proc.terminate()
        await proc.wait()


@pytest.mark.pw_integration
@pytest.mark.asyncio
async def test_capture_local_html(prerequisites_met, temp_output):
    """Test capturing a local HTML file served via HTTP server."""
    # Create a simple HTML file
    with tempfile.TemporaryDirectory() as tmpdir:
        html_dir = Path(tmpdir)
        html_file = html_dir / "test.html"
        html_file.write_text(
            """<!DOCTYPE html>
<html>
<head><title>Test Page</title></head>
<body>
    <h1>Hello World</h1>
    <p>This is a test page for Playwright capture.</p>
</body>
</html>"""
        )

        # Start a simple HTTP server
        server_proc = await asyncio.create_subprocess_exec(
            "python3",
            "-m",
            "http.server",
            "8765",
            cwd=str(html_dir),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Give server time to start
        await asyncio.sleep(1)

        try:
            proc, tmp = await _spawn_server()
            try:
                await _init_server(proc)

                result = await _call_tool(
                    proc,
                    "capture_url",
                    {
                        "url": "http://localhost:8765/test.html",
                        "output_path": str(temp_output),
                        "duration": 1.0,
                        "viewport_width": 800,
                        "viewport_height": 600,
                    },
                )

                assert "result" in result
                if temp_output.exists():
                    assert temp_output.stat().st_size > 0
                    # Check it's a valid video
                    import subprocess

                    probe_result = subprocess.run(
                        ["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(temp_output)],
                        capture_output=True,
                        text=True,
                    )
                    if probe_result.returncode == 0:
                        duration = float(probe_result.stdout.strip())
                        assert duration > 0

            finally:
                proc.terminate()
                await proc.wait()

        finally:
            server_proc.terminate()
            await server_proc.wait()
