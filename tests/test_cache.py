"""Unit tests for :mod:`videoflow.cache` — M7 cache layer."""

from __future__ import annotations

from pathlib import Path

import pytest

from videoflow.cache import CacheKey, CacheStore


class TestCacheKey:
    def test_same_inputs_same_key(self):
        a = CacheKey.from_tts("hello", "zh-CN-YunxiNeural", "+0%", "+0Hz")
        b = CacheKey.from_tts("hello", "zh-CN-YunxiNeural", "+0%", "+0Hz")
        assert a == b
        assert a.digest == b.digest
        assert len(a.digest) == 64  # SHA256 hex

    def test_different_text_different_key(self):
        a = CacheKey.from_tts("hello", "zh-CN", "+0%", "+0Hz")
        b = CacheKey.from_tts("world", "zh-CN", "+0%", "+0Hz")
        assert a != b

    def test_different_voice_different_key(self):
        a = CacheKey.from_tts("hello", "zh-CN-YunxiNeural", "+0%", "+0Hz")
        b = CacheKey.from_tts("hello", "zh-CN-XiaoxiaoNeural", "+0%", "+0Hz")
        assert a != b

    def test_kind_namespacing(self):
        """Same params under different kinds must produce different digests."""
        tts = CacheKey.from_parts("tts", "hello")
        visual = CacheKey.from_parts("visual", "hello")
        assert tts != visual

    def test_separator_collision_resistance(self):
        """(a, bc) and (ab, c) must not collide because of the unit separator."""
        a = CacheKey.from_parts("x", "a", "bc")
        b = CacheKey.from_parts("x", "ab", "c")
        assert a != b


class TestCacheStore:
    def test_miss_returns_none(self, tmp_path: Path):
        store = CacheStore(tmp_path / "cache")
        key = CacheKey.from_tts("hi", "v", "+0%", "+0Hz")
        assert store.get(key, kind="tts", ext="mp3") is None

    def test_put_then_get_roundtrips(self, tmp_path: Path):
        store = CacheStore(tmp_path / "cache")
        src = tmp_path / "payload.mp3"
        src.write_bytes(b"ID3\x00\x00\x00\x00\x00fake")

        key = CacheKey.from_tts("hi", "v", "+0%", "+0Hz")
        dest = store.put(key, src, kind="tts", ext="mp3")
        assert dest.exists()
        assert dest.read_bytes() == src.read_bytes()

        hit = store.get(key, kind="tts", ext="mp3")
        assert hit == dest

    def test_put_move_removes_source(self, tmp_path: Path):
        store = CacheStore(tmp_path / "cache")
        src = tmp_path / "payload.mp3"
        src.write_bytes(b"moveme")

        key = CacheKey.from_tts("hi", "v", "+0%", "+0Hz")
        dest = store.put(key, src, kind="tts", ext="mp3", move=True)
        assert dest.exists()
        assert not src.exists()
        assert dest.read_bytes() == b"moveme"

    def test_kind_subdirectories(self, tmp_path: Path):
        """Different kinds go to different subdirs so ``du -sh`` is useful."""
        store = CacheStore(tmp_path / "cache")
        src = tmp_path / "src"
        src.write_bytes(b"data")

        key = CacheKey.from_parts("x", "y")
        store.put(key, src, kind="tts", ext="mp3")
        store.put(key, src, kind="visual", ext="png")

        assert (tmp_path / "cache" / "tts").is_dir()
        assert (tmp_path / "cache" / "visual").is_dir()

    def test_size_aggregates(self, tmp_path: Path):
        store = CacheStore(tmp_path / "cache")
        src = tmp_path / "src"
        src.write_bytes(b"x" * 1000)

        k1 = CacheKey.from_parts("tts", "a")
        k2 = CacheKey.from_parts("tts", "b")
        store.put(k1, src, kind="tts", ext="mp3")
        store.put(k2, src, kind="tts", ext="mp3")
        assert store.size() == 2000
        assert store.size(kind="tts") == 2000
        assert store.size(kind="visual") == 0

    def test_clear_all_kinds(self, tmp_path: Path):
        store = CacheStore(tmp_path / "cache")
        src = tmp_path / "src"
        src.write_bytes(b"data")
        store.put(CacheKey.from_parts("a", "1"), src, kind="tts", ext="mp3")
        store.put(CacheKey.from_parts("b", "2"), src, kind="visual", ext="png")

        assert store.clear() == 2
        assert store.size() == 0

    def test_clear_single_kind(self, tmp_path: Path):
        store = CacheStore(tmp_path / "cache")
        src = tmp_path / "src"
        src.write_bytes(b"data")
        store.put(CacheKey.from_parts("a", "1"), src, kind="tts", ext="mp3")
        store.put(CacheKey.from_parts("b", "2"), src, kind="visual", ext="png")

        assert store.clear(kind="tts") == 1
        assert store.size(kind="tts") == 0
        assert store.size(kind="visual") > 0

    def test_get_or_put_misses_then_hits(self, tmp_path: Path):
        store = CacheStore(tmp_path / "cache")
        calls = {"n": 0}

        def producer(path: Path) -> None:
            calls["n"] += 1
            path.write_bytes(b"produced")

        key = CacheKey.from_parts("x", "y")
        p1 = store.get_or_put(key, kind="tts", ext="mp3", producer=producer)
        p2 = store.get_or_put(key, kind="tts", ext="mp3", producer=producer)

        assert p1 == p2
        assert calls["n"] == 1  # Second call should be a hit.
        assert p1.read_bytes() == b"produced"
