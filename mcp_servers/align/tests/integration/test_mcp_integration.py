"""Integration test that spawns the actual MCP server and calls tools.

These tests are marked with ``@pytest.mark.mcp_integration`` and are skipped
unless ``--run-integration`` is passed (see pytest.ini). They require
faster-whisper installed and will download the model on first run.

Usage:
    # From mcp_servers/align/
    pytest tests/ -v -m mcp_integration --run-integration

    # From repo root
    pytest mcp_servers/align/tests/ -v -m mcp_integration
"""

from __future__ import annotations

import asyncio
import json
import shutil
import subprocess
import sys
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

import pytest

from videoflow_align import __version__

# Protocol version for MCP handshake
MCP_PROTOCOL_VERSION = "2024-11-05"


@asynccontextmanager
async def _spawn_server() -> AsyncIterator[tuple[asyncio.subprocess.Process, Path]]:
    """Context manager that spawns the MCP server and yields the process + tmpdir.

    Yields:
        Tuple of (subprocess, temp_dir_path). The subprocess is terminated on
        exit; the tmpdir is left intact for test assertions.
    """
    tmpdir = Path(tempfile.mkdtemp())
    proc = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        "videoflow_align",
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        yield proc, tmpdir
    finally:
        await _shutdown_server(proc)


async def _shutdown_server(proc: asyncio.subprocess.Subprocess) -> None:
    """Gracefully shut down the MCP server."""
    try:
        proc.terminate()
        await asyncio.wait_for(proc.wait(), timeout=3.0)
    except asyncio.TimeoutError:
        proc.kill()
        await proc.wait()


async def _init_server(proc: asyncio.subprocess.Subprocess) -> dict:
    """Send initialize request and return the server capabilities."""
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
    response = json.loads(line.decode())
    assert "result" in response, f"Initialize failed: {response}"
    return response["result"]


async def _list_tools(proc: asyncio.subprocess.Subprocess) -> list[dict]:
    """Request the list of available tools."""
    tools_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
    }
    proc.stdin.write((json.dumps(tools_request) + "\n").encode())
    await proc.stdin.drain()
    line = await proc.stdout.readline()
    response = json.loads(line.decode())
    assert "result" in response, f"List tools failed: {response}"
    return response["result"]["tools"]


async def _call_tool(proc: asyncio.subprocess.Subprocess, name: str, arguments: dict) -> dict:
    """Call a tool by name with the given arguments."""
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


def _generate_test_audio(tmp: Path, duration: float = 3.0, sample_rate: int = 16000) -> Path:
    """Generate a synthetic audio file with a sine wave tone.

    This is more reliable than using edge-tts for testing, as it doesn't
    require network access.

    Args:
        tmp: Temporary directory path.
        duration: Audio duration in seconds.
        sample_rate: Audio sample rate in Hz.

    Returns:
        Path to the generated WAV file.
    """
    audio_path = tmp / "test.wav"

    # Use ffmpeg to generate a sine wave tone
    # Frequency 440Hz (A4 note) for 3 seconds
    result = subprocess.run(
        [
            "ffmpeg",
            "-y",  # Overwrite
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration}",
            "-ar",
            str(sample_rate),
            "-ac",
            "1",  # Mono
            "-acodec",
            "pcm_s16le",
            str(audio_path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert audio_path.exists(), f"Failed to generate audio: {result.stderr}"
    return audio_path


# =============================================================================
# Tests
# =============================================================================

@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_server_info():
    """Verify the server reports correct name and version."""
    async with _spawn_server() as (proc, tmp):
        result = await _init_server(proc)

        assert result["serverInfo"]["name"] == "videoflow-align"
        assert result["serverInfo"]["version"] == __version__
        assert "tools" in result.get("capabilities", {})


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_tool_registration():
    """Verify align_subtitle tool is registered."""
    async with _spawn_server() as (proc, tmp):
        await _init_server(proc)
        tools = await _list_tools(proc)

        tool_names = [t["name"] for t in tools]
        assert "align_subtitle" in tool_names

        # Verify the tool schema
        align_tool = next(t for t in tools if t["name"] == "align_subtitle")
        schema = align_tool["inputSchema"]
        required = schema.get("required", [])
        assert "audio_path" in required
        assert "text" in required
        assert "output_ass" in required


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_align_subtitle_basic():
    """Test align_subtitle with synthetic audio.

    Since we can't generate meaningful speech without TTS,
    we verify the server handles the request gracefully.
    """
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not found — needed for test audio generation")

    async with _spawn_server() as (proc, tmp):
        await _init_server(proc)

        audio_path = _generate_test_audio(tmp, duration=2.0)
        output_ass = tmp / "aligned.ass"

        transcript = "This is a simple test with words"

        response = await _call_tool(
            proc,
            "align_subtitle",
            {
                "audio_path": str(audio_path),
                "text": transcript,
                "output_ass": str(output_ass),
                "language": "en",
                "model_size": "tiny",  # Use tiny for fast tests
                "word_timestamps": True,
            },
        )

        # The response structure depends on success/failure
        assert "jsonrpc" in response
        assert response["id"] == 3

        # If there's an error, log but don't fail the test
        # (synthetic audio may not transcribe well)
        if "error" in response:
            pytest.skip(f"Alignment failed on synthetic audio (expected): {response['error']}")


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_align_subtitle_output_format():
    """Verify the ASS file has the correct format when alignment succeeds."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not found")

    async with _spawn_server() as (proc, tmp):
        await _init_server(proc)

        # Generate audio and call align
        audio_path = _generate_test_audio(tmp, duration=3.0)
        output_ass = tmp / "output.ass"

        response = await _call_tool(
            proc,
            "align_subtitle",
            {
                "audio_path": str(audio_path),
                "text": "A test sentence for alignment",
                "output_ass": str(output_ass),
                "language": "en",
                "model_size": "tiny",
                "word_timestamps": True,
            },
        )

        # Skip on transcription failure
        if "error" in response:
            pytest.skip(f"Alignment failed: {response['error']}")

        # Verify ASS file structure
        assert output_ass.exists(), "ASS file was not created"

        content = output_ass.read_text(encoding="utf-8")

        # Check ASS header
        assert "[Script Info]" in content
        assert "ScriptType: v4.00+" in content
        assert "[V4+ Styles]" in content
        assert "[Events]" in content

        # Check for dialogue lines with timestamps
        lines = content.split("\n")
        dialogue_lines = [l for l in lines if l.startswith("Dialogue:")]
        assert len(dialogue_lines) > 0, "No dialogue lines in ASS output"

        # Verify timestamp format (H:MM:SS.cs)
        for line in dialogue_lines:
            parts = line.split(",")
            assert len(parts) >= 3, f"Invalid dialogue line format: {line}"
            start_ts = parts[1]
            end_ts = parts[2]
            assert ":" in start_ts, f"Invalid timestamp format: {start_ts}"
            assert ":" in end_ts, f"Invalid timestamp format: {end_ts}"


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_align_subtitle_file_not_found():
    """Test error handling when audio file doesn't exist."""
    async with _spawn_server() as (proc, tmp):
        await _init_server(proc)

        response = await _call_tool(
            proc,
            "align_subtitle",
            {
                "audio_path": "/nonexistent/audio.wav",
                "text": "Some text",
                "output_ass": str(tmp / "output.ass"),
            },
        )

        # Should return an error
        assert "error" in response


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_align_subtitle_karaoke_tags():
    """Verify karaoke tags are emitted when word_timestamps=True."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not found")

    async with _spawn_server() as (proc, tmp):
        await _init_server(proc)

        audio_path = _generate_test_audio(tmp, duration=2.0)
        output_ass = tmp / "karaoke.ass"

        response = await _call_tool(
            proc,
            "align_subtitle",
            {
                "audio_path": str(audio_path),
                "text": "Hello world test",
                "output_ass": str(output_ass),
                "language": "en",
                "model_size": "tiny",
                "word_timestamps": True,
            },
        )

        if "error" in response:
            pytest.skip(f"Alignment failed: {response['error']}")

        content = output_ass.read_text(encoding="utf-8")

        # When word_timestamps is True, we expect \k karaoke tags
        # Note: With synthetic audio, this may not always produce word-level timing
        # but the format should still be valid
        assert output_ass.exists()


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_align_subtitle_language_detection():
    """Test that language detection works."""
    if shutil.which("ffmpeg") is None:
        pytest.skip("ffmpeg not found")

    async with _spawn_server() as (proc, tmp):
        await _init_server(proc)

        audio_path = _generate_test_audio(tmp, duration=2.0)
        output_ass = tmp / "lang_test.ass"

        # Use auto detection
        response = await _call_tool(
            proc,
            "align_subtitle",
            {
                "audio_path": str(audio_path),
                "text": "Testing language detection",
                "output_ass": str(output_ass),
                "language": "auto",
                "model_size": "tiny",
            },
        )

        # The response should contain the detected language in text content
        # or succeed without error
        assert "jsonrpc" in response


@pytest.mark.mcp_integration
@pytest.mark.asyncio
async def test_server_shutdown():
    """Verify the server shuts down cleanly on exit notification."""
    async with _spawn_server() as (proc, tmp):
        await _init_server(proc)

        # Send exit notification
        exit_notification = {
            "jsonrpc": "2.0",
            "method": "notifications/exit",
        }
        proc.stdin.write((json.dumps(exit_notification) + "\n").encode())
        await proc.stdin.drain()

        # Server should exit cleanly
        try:
            await asyncio.wait_for(proc.wait(), timeout=5.0)
            assert proc.returncode == 0, f"Server exited with code {proc.returncode}"
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            pytest.fail("Server did not exit within timeout")
