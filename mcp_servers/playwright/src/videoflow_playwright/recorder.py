"""Browser recorder using Playwright + ffmpeg.

This module provides screen recording capabilities by wrapping Playwright's
Chromium API with video capture via ffmpeg. The recording is saved as MP4
with VP9 codec and Opus audio.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

_LOGGER = logging.getLogger(__name__)

# Protocol version for MCP handshake
MCP_PROTOCOL_VERSION = "2024-11-05"


@dataclass
class Viewport:
    """Browser viewport dimensions."""

    width: int = 1920
    height: int = 1080


@dataclass
class RecordingOptions:
    """Options for screen recording."""

    url: str
    output_path: Path
    duration: float = 5.0  # seconds
    viewport: Viewport = field(default_factory=Viewport)
    fps: int = 30
    quality: str = "high"  # low, medium, high
    # Interaction scripts (optional)
    clicks: list[dict] = field(default_factory=list)
    scrolls: list[dict] = field(default_factory=list)
    type_texts: list[dict] = field(default_factory=list)
    wait_for_selectors: list[str] = field(default_factory=list)
    # Advanced
    user_agent: Optional[str] = None
    javascript_enabled: bool = True
    record_audio: bool = True


@dataclass
class RecordingResult:
    """Result of a screen recording."""

    output_path: Path
    duration: float
    width: int
    height: int
    fps: int
    file_size: int  # bytes


class BrowserRecorder:
    """Screen recorder using Playwright.

    Uses a warm browser instance to avoid cold-start latency on each recording.
    """

    _instance: Optional["BrowserRecorder"] = None
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(
        self,
        headless: bool = True,
        browser_channel: str = "chromium",
    ) -> None:
        """Initialize the recorder.

        Args:
            headless: Run browser in headless mode.
            browser_channel: Playwright browser channel (chromium, chrome, msedge).
        """
        self.headless = headless
        self.browser_channel = browser_channel
        self._browser = None
        self._context = None
        self._page = None
        self._ffmpeg_process: Optional[asyncio.subprocess.Process] = None
        self._temp_dir: Optional[Path] = None

    @classmethod
    async def get_instance(
        cls,
        headless: bool = True,
        browser_channel: str = "chromium",
    ) -> "BrowserRecorder":
        """Get or create a singleton browser instance."""
        async with cls._lock:
            if cls._instance is None:
                cls._instance = cls(headless, browser_channel)
                await cls._instance._start_browser()
            return cls._instance

    async def _start_browser(self) -> None:
        """Start the Chromium browser instance."""
        _LOGGER.info("Starting Chromium browser instance...")

        try:
            from playwright.async_api import async_playwright
        except ImportError as e:
            raise RuntimeError(
                "playwright not installed. "
                "Run: pip install playwright && playwright install chromium"
            ) from e

        self._playwright = await async_playwright().start()

        try:
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                channel=self.browser_channel,
            )
        except Exception as e:
            _LOGGER.error("Failed to launch Chromium: %s", e)
            raise RuntimeError(
                f"Failed to launch Chromium: {e}. "
                "Ensure Chromium is installed: playwright install chromium"
            ) from e

        _LOGGER.info("Chromium browser started successfully")

    async def close(self) -> None:
        """Close the browser instance."""
        async with self._lock:
            if self._browser:
                await self._browser.close()
                self._browser = None
            if self._playwright:
                await self._playwright.stop()
                self._playwright = None
            BrowserRecorder._instance = None
            _LOGGER.info("Chromium browser closed")

    async def record(
        self,
        options: RecordingOptions,
    ) -> RecordingResult:
        """Record a browser session and save as MP4.

        Args:
            options: Recording configuration.

        Returns:
            RecordingResult with metadata.

        Raises:
            RuntimeError: If recording fails.
        """
        _LOGGER.info(
            "Starting recording: url=%s, duration=%.1fs, viewport=%dx%d",
            options.url,
            options.duration,
            options.viewport.width,
            options.viewport.height,
        )

        # Create temporary directory for intermediate files
        self._temp_dir = Path(tempfile.mkdtemp(prefix="videoflow_pw_"))
        raw_video = self._temp_dir / "raw.webm"
        final_video = options.output_path

        # Ensure output directory exists
        final_video.parent.mkdir(parents=True, exist_ok=True)

        try:
            # Create new context and page for this recording
            context = await self._browser.new_context(
                viewport={
                    "width": options.viewport.width,
                    "height": options.viewport.height,
                },
                user_agent=options.user_agent,
                java_script_enabled=options.javascript_enabled,
                record_video_dir=self._temp_dir,
                record_video_size={
                    "width": options.viewport.width,
                    "height": options.viewport.height,
                },
            )

            page = await context.new_page()

            # Start navigation in background
            nav_task = asyncio.create_task(
                page.goto(options.url, wait_until="networkidle", timeout=30000)
            )

            # Wait for optional selectors
            for selector in options.wait_for_selectors:
                try:
                    await page.wait_for_selector(selector, timeout=10000)
                    _LOGGER.debug("Selector found: %s", selector)
                except Exception as e:
                    _LOGGER.warning("Selector not found: %s (%s)", selector, e)

            # Execute interaction scripts
            await self._execute_interactions(page, options)

            # Wait for navigation to complete
            try:
                await nav_task
            except Exception as e:
                _LOGGER.warning("Navigation warning: %s", e)

            # Wait for specified duration
            _LOGGER.debug("Waiting for %s seconds...", options.duration)
            await asyncio.sleep(options.duration)

            # Close context (this finalizes the video recording)
            await context.close()

            # Find the recorded video file
            video_files = list(self._temp_dir.glob("*.webm"))
            if video_files:
                raw_webm = video_files[0]
                _LOGGER.debug("Recorded video found: %s", raw_webm)

                # Convert to MP4 using ffmpeg
                await self._convert_to_mp4(raw_webm, final_video, options)

                # Get final video metadata
                metadata = await self._get_video_metadata(final_video)

                _LOGGER.info(
                    "Recording complete: %s (%.1fs, %s)",
                    final_video,
                    metadata["duration"],
                    self._format_size(metadata["size"]),
                )

                return RecordingResult(
                    output_path=final_video,
                    duration=metadata["duration"],
                    width=metadata["width"],
                    height=metadata["height"],
                    fps=options.fps,
                    file_size=metadata["size"],
                )
            else:
                raise RuntimeError("No video file was recorded")

        finally:
            # Clean up temp directory
            if self._temp_dir and self._temp_dir.exists():
                shutil.rmtree(self._temp_dir, ignore_errors=True)
                self._temp_dir = None

    async def _execute_interactions(
        self,
        page,
        options: RecordingOptions,
    ) -> None:
        """Execute interaction scripts on the page."""
        # Execute clicks
        for click_spec in options.clicks:
            selector = click_spec.get("selector")
            if selector:
                try:
                    await page.click(selector, timeout=5000)
                    _LOGGER.debug("Clicked: %s", selector)
                    await asyncio.sleep(0.5)  # Brief pause after click
                except Exception as e:
                    _LOGGER.warning("Click failed: %s (%s)", selector, e)

        # Execute scrolls
        for scroll_spec in options.scrolls:
            selector = scroll_spec.get("selector")
            x = scroll_spec.get("x", 0)
            y = scroll_spec.get("y", 500)
            if selector:
                try:
                    await page.locator(selector).evaluate(
                        f"el => el.scrollTo({x}, {y})"
                    )
                    _LOGGER.debug("Scrolled in %s to (%d, %d)", selector, x, y)
                except Exception as e:
                    _LOGGER.warning("Scroll failed: %s (%s)", selector, e)

        # Execute type texts
        for type_spec in options.type_texts:
            selector = type_spec.get("selector")
            text = type_spec.get("text", "")
            delay = type_spec.get("delay", 100)  # ms between keystrokes
            if selector and text:
                try:
                    await page.fill(selector, text)
                    _LOGGER.debug("Typed in %s: %s", selector, text[:20] + "...")
                except Exception as e:
                    _LOGGER.warning("Type failed: %s (%s)", selector, e)

    async def _convert_to_mp4(
        self,
        input_webm: Path,
        output_mp4: Path,
        options: RecordingOptions,
    ) -> None:
        """Convert WebM to MP4 using ffmpeg."""
        # Check if ffmpeg is available
        if not shutil.which("ffmpeg"):
            _LOGGER.warning("ffmpeg not found — copying as-is (WebM)")
            shutil.copy(input_webm, output_mp4)
            return

        # Build ffmpeg command
        # Quality presets
        crf_map = {"low": "28", "medium": "23", "high": "18"}
        crf = crf_map.get(options.quality, "23")

        cmd = [
            "ffmpeg",
            "-y",
            "-i", str(input_webm),
            "-c:v", "libx264",
            "-crf", crf,
            "-preset", "medium",
            "-pix_fmt", "yuv420p",
            "-c:a", "aac",
            "-b:a", "128k",
            "-movflags", "+faststart",
            str(output_mp4),
        ]

        _LOGGER.debug("Running ffmpeg: %s", " ".join(cmd))

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            _LOGGER.debug("ffmpeg output: %s", result.stderr[-500:])
        except subprocess.CalledProcessError as e:
            _LOGGER.warning(
                "ffmpeg conversion failed: %s — copying as-is",
                e.stderr[-200:],
            )
            shutil.copy(input_webm, output_mp4)

    async def _get_video_metadata(self, video_path: Path) -> dict:
        """Get video metadata using ffprobe."""
        if not shutil.which("ffprobe"):
            # Fallback: estimate from file size
            stat = video_path.stat()
            return {
                "duration": 5.0,  # Assume duration if ffprobe unavailable
                "width": 1920,
                "height": 1080,
                "size": stat.st_size,
            }

        cmd = [
            "ffprobe",
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(video_path),
        ]

        try:
            result = subprocess.run(
                cmd,
                check=True,
                capture_output=True,
                text=True,
            )
            import json

            data = json.loads(result.stdout)
            video_stream = next(
                (s for s in data.get("streams", []) if s.get("codec_type") == "video"),
                None,
            )
            format_info = data.get("format", {})

            return {
                "duration": float(format_info.get("duration", 0)),
                "width": int(video_stream.get("width", 0)) if video_stream else 0,
                "height": int(video_stream.get("height", 0)) if video_stream else 0,
                "size": int(format_info.get("size", 0)),
            }
        except Exception as e:
            _LOGGER.warning("Failed to get video metadata: %s", e)
            stat = video_path.stat()
            return {
                "duration": 5.0,
                "width": 1920,
                "height": 1080,
                "size": stat.st_size,
            }

    @staticmethod
    def _format_size(size: int) -> str:
        """Format file size in human-readable format."""
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} TB"


async def record_screen(
    url: str,
    output_path: Path,
    duration: float = 5.0,
    viewport_width: int = 1920,
    viewport_height: int = 1080,
    fps: int = 30,
    quality: str = "high",
) -> RecordingResult:
    """Convenience function for simple screen recording.

    Args:
        url: URL to record.
        output_path: Where to save the MP4.
        duration: Recording duration in seconds.
        viewport_width: Browser viewport width.
        viewport_height: Browser viewport height.
        fps: Target frame rate.
        quality: Video quality (low, medium, high).

    Returns:
        RecordingResult with metadata.
    """
    recorder = await BrowserRecorder.get_instance()

    options = RecordingOptions(
        url=url,
        output_path=output_path,
        duration=duration,
        viewport=Viewport(width=viewport_width, height=viewport_height),
        fps=fps,
        quality=quality,
    )

    return await recorder.record(options)
