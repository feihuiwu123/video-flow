"""Content-addressable cache for pipeline artifacts (M7).

Design
------
* **Key = SHA-256(ordered params + body).** Every cached artifact has a
  deterministic key derived from everything that affects its bytes — e.g.
  TTS voice/rate/pitch/text. Equal params → equal key → cache hit.
* **Store = flat directory of <sha256>.<ext> files.** Simple, filesystem-
  truth-source, easy to inspect, easy to evict (``rm``).
* **Per-kind namespaces** so TTS MP3s don't collide with visual PNGs.
* **Opt-in.** ``CacheStore`` is threaded through ``run_pipeline`` as a
  keyword; legacy tests and demo runs pass ``None`` and skip caching
  entirely. This matches the project's "DB is an optional index" posture.

Typical wiring::

    cache = CacheStore(Path("cache"))
    key = CacheKey.from_tts(text, voice, rate, pitch)
    hit = cache.get(key, kind="tts", ext="mp3")
    if hit is None:
        tmp = workspace / f"{shot_id}.mp3"
        await provider.synthesize(text, tmp)
        hit = cache.put(key, tmp, kind="tts", ext="mp3", move=False)
    shot.audio_file = hit

We intentionally ship the cheap, understandable thing:

* No LRU or TTL. Cache grows until the user deletes it. ``CacheStore.size()``
  exists so a future eviction policy is easy to bolt on.
* No in-memory layer — disk is cheap and consistent across processes.
* Hits are returned as read-only ``Path`` handles; the caller is expected
  to treat them as immutable. If you need to mutate, copy first.
"""

from __future__ import annotations

import hashlib
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class CacheKey:
    """A stable content hash for a pipeline artifact.

    We embed the *kind* (``tts``, ``visual``, ``stock`` …) in the hash
    input so "same text, different renderer" can't collide. The resulting
    hex digest is the filename stem on disk.
    """

    digest: str

    def __str__(self) -> str:
        return self.digest

    @classmethod
    def from_parts(cls, kind: str, *parts: object) -> "CacheKey":
        """Build a key from ``kind`` and an ordered tuple of params.

        Each part is coerced to string and joined with a separator that
        cannot appear in TTS voice IDs / hex colours / paths, so distinct
        parameter tuples hash distinctly.
        """
        h = hashlib.sha256()
        h.update(kind.encode("utf-8"))
        h.update(b"\x1f")  # ASCII unit separator — unlikely in user input
        for p in parts:
            h.update(str(p).encode("utf-8"))
            h.update(b"\x1f")
        return cls(digest=h.hexdigest())

    @classmethod
    def from_tts(cls, text: str, voice: str, rate: str, pitch: str) -> "CacheKey":
        """TTS key = (voice, rate, pitch, text)."""
        return cls.from_parts("tts", voice, rate, pitch, text)

    @classmethod
    def from_visual(
        cls,
        shot_id: str,
        visual_repr: str,
        width: int,
        height: int,
        background_color: str,
    ) -> "CacheKey":
        """Visual PNG key = (shot_id, visual repr, dimensions, bg).

        ``visual_repr`` should be a stable serialisation of the VisualSpec
        (e.g. ``model_dump_json()`` on a Pydantic model). ``shot_id`` is
        included so renaming a shot in place doesn't hit a stale frame.
        """
        return cls.from_parts(
            "visual", shot_id, visual_repr, width, height, background_color
        )

    @classmethod
    def from_stock(cls, query: str, provider: str) -> "CacheKey":
        """Stock footage key = (provider, query)."""
        return cls.from_parts("stock", provider, query)


class CacheStore:
    """On-disk cache rooted at ``root_dir``.

    Kinds get their own subdirectory so ``ls`` and ``du`` produce useful
    output. ``root_dir`` is created on first use.
    """

    def __init__(self, root_dir: Path) -> None:
        self.root_dir = Path(root_dir)

    # --- low-level layout -----------------------------------------------

    def _kind_dir(self, kind: str) -> Path:
        return self.root_dir / kind

    def path_for(self, key: CacheKey, kind: str, ext: str) -> Path:
        """Return the canonical path for ``(key, kind, ext)`` without
        checking existence. Useful when writing directly."""
        return self._kind_dir(kind) / f"{key.digest}.{ext.lstrip('.')}"

    # --- hit / miss -----------------------------------------------------

    def get(self, key: CacheKey, kind: str, ext: str) -> Optional[Path]:
        """Return the cached path for ``key`` or ``None`` on miss."""
        candidate = self.path_for(key, kind, ext)
        if candidate.exists():
            _LOGGER.debug("cache HIT %s/%s", kind, key.digest[:12])
            return candidate
        _LOGGER.debug("cache MISS %s/%s", kind, key.digest[:12])
        return None

    def put(
        self,
        key: CacheKey,
        source_path: Path,
        kind: str,
        ext: str,
        *,
        move: bool = False,
    ) -> Path:
        """Insert ``source_path`` into the cache and return the cached path.

        Args:
            move: If True, the source is *moved* (os.replace) into cache —
                cheap when the producer wrote to a tmpdir. If False, copied.
        """
        dest = self.path_for(key, kind, ext)
        dest.parent.mkdir(parents=True, exist_ok=True)
        if move:
            # ``Path.replace`` is atomic within a filesystem; if the caller
            # crossed filesystems they get a clearer error than shutil.move.
            Path(source_path).replace(dest)
        else:
            shutil.copy2(source_path, dest)
        _LOGGER.info("cache PUT %s/%s", kind, key.digest[:12])
        return dest

    def get_or_put(
        self,
        key: CacheKey,
        kind: str,
        ext: str,
        producer,  # Callable[[Path], None] — writes to the given path.
    ) -> Path:
        """Synchronous convenience: return cached path, producing if missing.

        ``producer(tmp_path)`` is called on miss; it must populate the given
        path (no return value needed). This is for rare callers that can
        run synchronously — most real callers use the async variant below.
        """
        hit = self.get(key, kind, ext)
        if hit is not None:
            return hit
        dest = self.path_for(key, kind, ext)
        dest.parent.mkdir(parents=True, exist_ok=True)
        producer(dest)
        _LOGGER.info("cache MISS→WRITE %s/%s", kind, key.digest[:12])
        return dest

    # --- introspection / eviction --------------------------------------

    def size(self, kind: Optional[str] = None) -> int:
        """Total bytes of cached artifacts under ``kind`` (or all if None)."""
        root = self._kind_dir(kind) if kind else self.root_dir
        if not root.exists():
            return 0
        return sum(f.stat().st_size for f in root.rglob("*") if f.is_file())

    def clear(self, kind: Optional[str] = None) -> int:
        """Delete cached files; return number of files removed."""
        root = self._kind_dir(kind) if kind else self.root_dir
        if not root.exists():
            return 0
        count = 0
        for f in root.rglob("*"):
            if f.is_file():
                f.unlink()
                count += 1
        return count


__all__ = ["CacheKey", "CacheStore"]
