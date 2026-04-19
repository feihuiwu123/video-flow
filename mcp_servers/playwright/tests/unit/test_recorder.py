"""Unit tests for videoflow-playwright recorder."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from videoflow_playwright.recorder import (
    BrowserRecorder,
    RecordingOptions,
    Viewport,
)


class TestViewport:
    """Tests for Viewport dataclass."""

    def test_default_values(self):
        """Test default viewport dimensions."""
        vp = Viewport()
        assert vp.width == 1920
        assert vp.height == 1080

    def test_custom_values(self):
        """Test custom viewport dimensions."""
        vp = Viewport(width=1280, height=720)
        assert vp.width == 1280
        assert vp.height == 720


class TestRecordingOptions:
    """Tests for RecordingOptions dataclass."""

    def test_required_fields(self, tmp_path):
        """Test that required fields work."""
        output = tmp_path / "test.mp4"
        opts = RecordingOptions(url="https://example.com", output_path=output)
        assert opts.url == "https://example.com"
        assert opts.output_path == output

    def test_default_values(self, tmp_path):
        """Test default options."""
        output = tmp_path / "test.mp4"
        opts = RecordingOptions(url="https://example.com", output_path=output)
        assert opts.duration == 5.0
        assert opts.viewport == Viewport()
        assert opts.fps == 30
        assert opts.quality == "high"
        assert opts.clicks == []
        assert opts.scrolls == []
        assert opts.type_texts == []
        assert opts.wait_for_selectors == []

    def test_custom_options(self, tmp_path):
        """Test custom options."""
        output = tmp_path / "test.mp4"
        opts = RecordingOptions(
            url="https://example.com",
            output_path=output,
            duration=10.0,
            viewport=Viewport(width=800, height=600),
            fps=60,
            quality="low",
            clicks=[{"selector": "#btn"}],
            scrolls=[{"selector": "body", "x": 0, "y": 100}],
            type_texts=[{"selector": "input", "text": "hello"}],
            wait_for_selectors=[".content"],
        )
        assert opts.duration == 10.0
        assert opts.viewport.width == 800
        assert opts.viewport.height == 600
        assert opts.fps == 60
        assert opts.quality == "low"
        assert len(opts.clicks) == 1
        assert len(opts.scrolls) == 1
        assert len(opts.type_texts) == 1
        assert len(opts.wait_for_selectors) == 1


class TestBrowserRecorder:
    """Tests for BrowserRecorder class."""

    def test_singleton_lock(self):
        """Test that singleton uses a lock."""
        assert BrowserRecorder._lock is not None

    def test_format_size(self):
        """Test file size formatting."""
        assert "512.0 B" in BrowserRecorder._format_size(512)
        assert "1.0 KB" in BrowserRecorder._format_size(1024)
        assert "1.0 MB" in BrowserRecorder._format_size(1024 * 1024)
        assert "1.0 GB" in BrowserRecorder._format_size(1024 * 1024 * 1024)


class TestRecordingOptionsValidation:
    """Tests for RecordingOptions validation."""

    def test_url_validation(self, tmp_path):
        """URL should accept any string."""
        output = tmp_path / "out.mp4"
        # Should not raise
        opts = RecordingOptions(url="http://example.com", output_path=output)
        assert opts.url == "http://example.com"

    def test_duration_validation(self, tmp_path):
        """Duration should accept float values."""
        output = tmp_path / "out.mp4"
        opts = RecordingOptions(
            url="https://example.com",
            output_path=output,
            duration=0.5,
        )
        assert opts.duration == 0.5

    def test_quality_validation(self, tmp_path):
        """Quality should be one of the allowed values."""
        output = tmp_path / "out.mp4"
        for quality in ["low", "medium", "high"]:
            opts = RecordingOptions(
                url="https://example.com",
                output_path=output,
                quality=quality,
            )
            assert opts.quality == quality
