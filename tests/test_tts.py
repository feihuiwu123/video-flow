"""Unit tests for videoflow.tts (mocked — no network)."""

from pathlib import Path

import pytest

from videoflow.tts import TTSProvider, synthesize_all


class FakeProvider(TTSProvider):
    def __init__(self, durations: dict[str, float]):
        self._durations = durations
        self.calls: list[tuple[str, Path]] = []

    async def synthesize(self, text: str, output_path: Path) -> float:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"\x00")  # tiny placeholder
        self.calls.append((text, output_path))
        # Deterministic: hash text length → duration.
        return self._durations[text]


@pytest.mark.asyncio
async def test_synthesize_all_returns_all_durations(tmp_path):
    items = [
        ("S01", "hello", tmp_path / "S01.mp3"),
        ("S02", "world there", tmp_path / "S02.mp3"),
    ]
    provider = FakeProvider({"hello": 1.2, "world there": 2.7})
    out = await synthesize_all(provider, items)
    assert out == {"S01": 1.2, "S02": 2.7}
    assert (tmp_path / "S01.mp3").exists()
    assert (tmp_path / "S02.mp3").exists()


@pytest.mark.asyncio
async def test_synthesize_all_respects_concurrency(tmp_path):
    items = [(f"S{i:02d}", f"text{i}", tmp_path / f"S{i:02d}.mp3") for i in range(5)]
    provider = FakeProvider({f"text{i}": float(i) + 1 for i in range(5)})
    out = await synthesize_all(provider, items, max_concurrency=2)
    assert set(out.keys()) == {f"S{i:02d}" for i in range(5)}
    assert len(provider.calls) == 5


@pytest.mark.asyncio
async def test_synthesize_all_empty_input(tmp_path):
    provider = FakeProvider({})
    out = await synthesize_all(provider, [])
    assert out == {}
