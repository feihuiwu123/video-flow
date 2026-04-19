"""Unit tests for WhisperEngine.

faster-whisper is intentionally NOT a test-time dependency — these tests
inject a fake ``faster_whisper`` module into ``sys.modules`` so ``engine.py``'s
lazy import inside ``_ensure_model`` picks it up.
"""

from __future__ import annotations

import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from videoflow_align.engine import WhisperEngine, align_audio_with_text


# --- fake faster_whisper module -------------------------------------------

def _make_fake_whisper_model() -> MagicMock:
    """Build a MagicMock that mimics ``faster_whisper.WhisperModel``.

    The real class returns ``(segments_iter, info)`` from ``.transcribe(...)``.
    """
    mock_word1 = MagicMock(word="Hello", start=0.0, end=1.2, probability=0.95)
    mock_word2 = MagicMock(word="world", start=1.2, end=2.5, probability=0.92)
    mock_segment = MagicMock(
        start=0.0, end=2.5, text="Hello world", words=[mock_word1, mock_word2]
    )
    mock_info = MagicMock(language="en", language_probability=0.99)

    model = MagicMock()
    model.transcribe.return_value = ([mock_segment], mock_info)
    return model


@pytest.fixture
def fake_faster_whisper(monkeypatch):
    """Install a fake ``faster_whisper`` module so the lazy import resolves."""
    model = _make_fake_whisper_model()

    fake_module = types.ModuleType("faster_whisper")
    # The engine does ``from faster_whisper import WhisperModel`` so we need
    # ``WhisperModel(...)`` to return our mock instance.
    whisper_class = MagicMock(return_value=model)
    fake_module.WhisperModel = whisper_class  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "faster_whisper", fake_module)
    # Yield the class so tests can inspect call args.
    yield whisper_class, model


# --- tests ----------------------------------------------------------------


def test_whisper_engine_lazy_load(fake_faster_whisper):
    """Model is only loaded on first transcribe call."""
    _cls, model = fake_faster_whisper
    engine = WhisperEngine(model_size="base")
    assert engine._model is None  # Nothing loaded yet.

    segments, lang = engine.transcribe(Path("dummy.mp3"))

    assert engine._model is model
    assert lang == "en"
    assert len(segments) == 1
    assert segments[0].text == "Hello world"
    assert len(segments[0].words) == 2


def test_whisper_engine_parameters(fake_faster_whisper):
    """Constructor + transcribe pass their args to faster-whisper."""
    whisper_class, model = fake_faster_whisper
    engine = WhisperEngine(
        model_size="small",
        device="cuda",
        compute_type="float16",
        language="zh",
    )
    engine.transcribe(
        Path("test.mp3"),
        prompt_text="Some prompt",
        word_timestamps=False,
        beam_size=3,
        vad_filter=False,
    )

    whisper_class.assert_called_once()
    ctor_kwargs = whisper_class.call_args.kwargs
    assert ctor_kwargs["model_size_or_path"] == "small"
    assert ctor_kwargs["device"] == "cuda"
    assert ctor_kwargs["compute_type"] == "float16"

    model.transcribe.assert_called_once()
    t_kwargs = model.transcribe.call_args.kwargs
    assert t_kwargs["language"] == "zh"
    assert t_kwargs["initial_prompt"] == "Some prompt"
    assert t_kwargs["word_timestamps"] is False
    assert t_kwargs["beam_size"] == 3
    assert t_kwargs["vad_filter"] is False


def test_align_audio_with_text(fake_faster_whisper):
    """High-level convenience function returns the engine's output."""
    segments, lang = align_audio_with_text(
        audio_path=Path("audio.mp3"),
        text="Expected transcript",
        language="en",
        model_size="base",
        word_timestamps=True,
    )
    assert lang == "en"
    assert len(segments) == 1


def test_align_audio_with_text_auto_language(fake_faster_whisper):
    """``language='auto'`` is translated to ``None`` when instantiating the engine."""
    whisper_class, _model = fake_faster_whisper
    _, _lang = align_audio_with_text(
        audio_path=Path("audio.mp3"),
        text="Text",
        language="auto",
    )
    # The WhisperModel constructor doesn't take ``language``; language is
    # passed per-call. Verify the engine calls ``model.transcribe(language=None)``.
    model = whisper_class.return_value
    t_kwargs = model.transcribe.call_args.kwargs
    assert t_kwargs["language"] is None


def test_engine_missing_faster_whisper(monkeypatch):
    """If faster_whisper is not importable, ``_ensure_model`` raises a helpful error."""
    # Hide any previously-loaded ``faster_whisper`` to force an ImportError.
    monkeypatch.setitem(sys.modules, "faster_whisper", None)

    engine = WhisperEngine()
    with pytest.raises(RuntimeError, match="faster-whisper not installed"):
        engine._ensure_model()
