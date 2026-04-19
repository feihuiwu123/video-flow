"""Transcription & alignment engine using faster-whisper.

This module houses the heavy ML dependency (faster-whisper + ctranslate2)
and should be kept as a leaf module so unit tests can mock it away.
"""

from __future__ import annotations

import logging
import warnings
from pathlib import Path
from typing import Optional

from .ass_writer import Segment, WordTiming

# faster-whisper is heavy; we import lazily inside functions so unit tests
# can patch before the import happens.
# Model cache is handled by faster-whisper itself (~/.cache/huggingface/).

_LOGGER = logging.getLogger(__name__)


class WhisperEngine:
    """Wrapper around faster-whisper with word-level timestamps.

    Model loading is lazy — first call to `transcribe` will download the
    model if needed.
    """

    def __init__(
        self,
        model_size: str = "base",
        device: str = "cpu",
        compute_type: str = "int8",
        download_root: Optional[Path] = None,
        language: Optional[str] = None,
    ) -> None:
        """Initialize engine (does NOT load model yet).

        Args:
            model_size: "tiny", "base", "small", "medium", "large-v1", "large-v2"
            device: "cpu", "cuda", "auto"
            compute_type: "int8", "int8_float16", "float16", "float32"
            download_root: Where to cache the model (default: ~/.cache/huggingface/)
            language: Force language (ISO code) or None for auto-detection.
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.download_root = str(download_root) if download_root else None
        self.language = language

        self._model = None  # Lazily loaded
        self._suppress_warnings()

    def _suppress_warnings(self) -> None:
        """Silence some of the more verbose warnings from the stack."""
        # faster-whisper uses transformers, which may spam about tokenizers.
        warnings.filterwarnings("ignore", category=UserWarning, module="transformers")

    def _ensure_model(self) -> None:
        """Lazy-load the faster-whisper model."""
        if self._model is not None:
            return

        _LOGGER.info("Loading faster-whisper %s model...", self.model_size)
        try:
            from faster_whisper import WhisperModel
        except ImportError as e:
            raise RuntimeError(
                "faster-whisper not installed. "
                "Run `pip install faster-whisper` in this environment."
            ) from e

        self._model = WhisperModel(
            model_size_or_path=self.model_size,
            device=self.device,
            compute_type=self.compute_type,
            download_root=self.download_root,
        )
        _LOGGER.info("Model loaded.")

    def transcribe(
        self,
        audio_path: Path,
        prompt_text: Optional[str] = None,
        word_timestamps: bool = True,
        beam_size: int = 5,
        vad_filter: bool = True,
        vad_parameters: Optional[dict] = None,
    ) -> tuple[list[Segment], str]:
        """Transcribe audio with word-level timestamps.

        Args:
            audio_path: Path to audio file (MP3, WAV, etc.).
            prompt_text: Optional initial prompt (helps with terminology).
            word_timestamps: If True, include word-level timing.
            beam_size: Beam size for decoding.
            vad_filter: Apply voice activity detection to remove silence.
            vad_parameters: Custom VAD parameters (see faster-whisper docs).

        Returns:
            Tuple of (segments, detected_language).
            Segments are sentence-level groupings with word timings inside.
        """
        self._ensure_model()

        # Prepare options
        if vad_parameters is None:
            vad_parameters = dict(
                threshold=0.5,
                min_speech_duration_ms=250,
                min_silence_duration_ms=2000,
            )

        _LOGGER.debug("Transcribing %s (prompt=%s)", audio_path, prompt_text)

        # faster-whisper expects string path
        segments, info = self._model.transcribe(
            str(audio_path),
            language=self.language,
            initial_prompt=prompt_text,
            word_timestamps=word_timestamps,
            beam_size=beam_size,
            vad_filter=vad_filter,
            vad_parameters=vad_parameters,
        )

        _LOGGER.debug("Detected language: %s (prob=%.3f)", info.language, info.language_probability)

        # Convert to our data types
        result_segments = []
        for seg in segments:
            words = []
            for word in seg.words:
                words.append(WordTiming(
                    word=word.word,
                    start=word.start,
                    end=word.end,
                    probability=word.probability,
                ))

            result_segments.append(Segment(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                words=words,
            ))

        return result_segments, info.language


def align_audio_with_text(
    audio_path: Path,
    text: str,
    language: str = "auto",
    model_size: str = "base",
    word_timestamps: bool = True,
) -> tuple[list[Segment], str]:
    """High-level convenience function for the MCP tool.

    This is what the `align_subtitle` tool will call.

    Args:
        audio_path: Audio file to transcribe.
        text: Reference transcript (used as prompt).
        language: ISO code or "auto" for detection.
        model_size: faster-whisper model size.
        word_timestamps: Include word-level timestamps.

    Returns:
        (segments, detected_language)
    """
    engine = WhisperEngine(
        model_size=model_size,
        language=None if language == "auto" else language,
    )

    # Use the text as a prompt to improve transcription accuracy
    return engine.transcribe(
        audio_path=audio_path,
        prompt_text=text,
        word_timestamps=word_timestamps,
    )