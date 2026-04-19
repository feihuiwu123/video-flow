"""Tests for TTS cache integration (M7.1)."""

from __future__ import annotations

import asyncio
from pathlib import Path
from typing import List

import pytest

from videoflow.cache import CacheKey, CacheStore
from videoflow.tts import TTSProvider, synthesize_all


class _FakeProvider(TTSProvider):
    """Counts synthesis calls and writes a deterministic stub MP3."""

    def __init__(self) -> None:
        self.calls: List[tuple[str, Path]] = []

    async def synthesize(self, text: str, output_path: Path) -> float:
        self.calls.append((text, output_path))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        # Minimal valid-ish MP3 header + payload. duration probe is mocked.
        output_path.write_bytes(b"ID3\x04\x00\x00\x00\x00\x00\x00" + text.encode())
        return 1.23


@pytest.fixture
def no_probe(monkeypatch):
    """Skip the ffprobe call — we're not rendering real audio."""
    monkeypatch.setattr("videoflow.tts.probe_duration", lambda p: 1.23)


def test_cache_miss_then_hit(tmp_path: Path, no_probe):
    cache = CacheStore(tmp_path / "cache")
    provider = _FakeProvider()

    items = [
        ("S01", "hello", tmp_path / "run1" / "S01.mp3"),
        ("S02", "world", tmp_path / "run1" / "S02.mp3"),
    ]
    params = {"voice": "v", "rate": "+0%", "pitch": "+0Hz"}

    durations = asyncio.run(
        synthesize_all(provider, items, cache=cache, cache_params=params)
    )
    assert set(durations) == {"S01", "S02"}
    assert len(provider.calls) == 2  # Both misses.

    # Second run with different output directory; same text/voice → 100% hits.
    items2 = [
        ("S01", "hello", tmp_path / "run2" / "S01.mp3"),
        ("S02", "world", tmp_path / "run2" / "S02.mp3"),
    ]
    durations2 = asyncio.run(
        synthesize_all(provider, items2, cache=cache, cache_params=params)
    )
    assert set(durations2) == {"S01", "S02"}
    assert len(provider.calls) == 2  # No additional work.
    assert (tmp_path / "run2" / "S01.mp3").exists()
    assert (tmp_path / "run2" / "S02.mp3").exists()


def test_same_text_different_voice_busts_cache(tmp_path: Path, no_probe):
    cache = CacheStore(tmp_path / "cache")
    provider = _FakeProvider()

    items = [("S01", "hello", tmp_path / "a" / "S01.mp3")]
    asyncio.run(synthesize_all(
        provider, items, cache=cache,
        cache_params={"voice": "v1", "rate": "+0%", "pitch": "+0Hz"},
    ))
    asyncio.run(synthesize_all(
        provider,
        [("S01", "hello", tmp_path / "b" / "S01.mp3")],
        cache=cache,
        cache_params={"voice": "v2", "rate": "+0%", "pitch": "+0Hz"},
    ))
    # Voice differs → both requests hit the provider.
    assert len(provider.calls) == 2


def test_cache_requires_params(tmp_path: Path):
    cache = CacheStore(tmp_path / "cache")
    provider = _FakeProvider()
    items = [("S01", "hi", tmp_path / "out.mp3")]
    with pytest.raises(ValueError, match="cache_params"):
        asyncio.run(synthesize_all(provider, items, cache=cache))


def test_no_cache_runs_unchanged(tmp_path: Path, no_probe):
    """Passing ``cache=None`` must behave exactly like the legacy pathway."""
    provider = _FakeProvider()
    items = [("S01", "hello", tmp_path / "S01.mp3")]
    durations = asyncio.run(synthesize_all(provider, items))
    assert durations["S01"] == 1.23
    assert len(provider.calls) == 1
