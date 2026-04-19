"""edge-tts wrapper for the demo.

Usage::

    from videoflow.tts import EdgeTTSProvider

    provider = EdgeTTSProvider(voice="zh-CN-YunxiNeural")
    duration = await provider.synthesize("你好", Path("/tmp/hi.mp3"))

The Provider base class mirrors the future MCP ``videoflow-tts`` contract so
it can be swapped for Azure/ElevenLabs without touching callers.
"""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from abc import ABC, abstractmethod
from pathlib import Path


class TTSProvider(ABC):
    """Abstract TTS provider — stable interface for Parser and Pipeline."""

    @abstractmethod
    async def synthesize(self, text: str, output_path: Path) -> float:
        """Generate audio for ``text`` at ``output_path``.

        Returns:
            Duration of the generated audio in seconds.
        """


class EdgeTTSProvider(TTSProvider):
    def __init__(
        self,
        voice: str = "zh-CN-YunxiNeural",
        rate: str = "+0%",
        pitch: str = "+0Hz",
    ) -> None:
        self.voice = voice
        self.rate = rate
        self.pitch = pitch

    async def synthesize(self, text: str, output_path: Path) -> float:
        # Imported lazily so unit tests can monkey-patch the module without
        # requiring edge-tts to be installed.
        import edge_tts  # type: ignore

        output_path.parent.mkdir(parents=True, exist_ok=True)
        communicator = edge_tts.Communicate(
            text=text,
            voice=self.voice,
            rate=self.rate,
            pitch=self.pitch,
        )
        await communicator.save(str(output_path))
        return probe_duration(output_path)


def probe_duration(path: Path) -> float:
    """Return the duration of an audio/video file via ``ffprobe``.

    Using ffprobe keeps the dependency footprint tiny (FFmpeg is already
    required by the composer).
    """
    if shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe not found — install FFmpeg to continue")
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return float(result.stdout.strip())


async def synthesize_all(
    provider: TTSProvider,
    items: list[tuple[str, str, Path]],
    max_concurrency: int = 4,
) -> dict[str, float]:
    """Synthesize multiple clips concurrently.

    Args:
        provider: TTS backend to call.
        items: Tuples of ``(shot_id, text, output_path)``.
        max_concurrency: Upper bound on in-flight ``synthesize`` calls.

    Returns:
        Mapping of ``shot_id`` to audio duration in seconds.
    """
    sem = asyncio.Semaphore(max_concurrency)

    async def _one(shot_id: str, text: str, path: Path) -> tuple[str, float]:
        async with sem:
            dur = await provider.synthesize(text, path)
        return shot_id, dur

    pairs = await asyncio.gather(*(_one(sid, txt, p) for sid, txt, p in items))
    return dict(pairs)
