"""ASS v4.00+ writer with word-level karaoke tags.

This module is pure Python — no faster-whisper dependency — so it can be
unit-tested without heavy ML installs. The transcription layer
(``engine.py``) converts faster-whisper's word objects into
``WordTiming`` dataclasses and hands them to :func:`write_ass`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class WordTiming:
    """One word with start/end seconds and probability."""

    word: str
    start: float  # seconds
    end: float  # seconds
    probability: float = 1.0

    def __post_init__(self) -> None:
        if self.end < self.start:
            raise ValueError(
                f"WordTiming end ({self.end}) < start ({self.start}) for {self.word!r}"
            )


@dataclass
class Segment:
    """A sentence-level segment containing one or more words."""

    start: float
    end: float
    text: str
    words: list[WordTiming] = field(default_factory=list)


@dataclass
class AssStyle:
    font_name: str = "PingFang SC"
    font_size: int = 56
    primary_color: str = "&H00FFFFFF"  # white
    secondary_color: str = "&H0000FFFF"  # yellow (karaoke highlight)
    outline_color: str = "&H00000000"  # black outline
    alignment: int = 2  # bottom-center
    margin_v: int = 200
    play_res_x: int = 1080
    play_res_y: int = 1920


def _fmt_timestamp(seconds: float) -> str:
    """ASS uses H:MM:SS.cs (centiseconds, single-digit hour)."""
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = seconds % 60
    whole = int(secs)
    cs = int(round((secs - whole) * 100))
    # Guard against rounding overflow (e.g. 9.999 → cs=100).
    if cs == 100:
        whole += 1
        cs = 0
        if whole == 60:
            whole = 0
            minutes += 1
            if minutes == 60:
                minutes = 0
                hours += 1
    return f"{hours}:{minutes:02d}:{whole:02d}.{cs:02d}"


def _escape_text(text: str) -> str:
    """Neutralise ASS override block characters and newlines."""
    return text.replace("{", "(").replace("}", ")").replace("\n", " ").replace("\r", "")


def _build_header(style: AssStyle) -> str:
    return (
        f"[Script Info]\n"
        f"ScriptType: v4.00+\n"
        f"PlayResX: {style.play_res_x}\n"
        f"PlayResY: {style.play_res_y}\n"
        f"WrapStyle: 2\n"
        f"ScaledBorderAndShadow: yes\n"
        f"\n"
        f"[V4+ Styles]\n"
        f"Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        f"OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        f"ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        f"Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{style.font_name},{style.font_size},"
        f"{style.primary_color},{style.secondary_color},{style.outline_color},"
        f"&H64000000,0,0,0,0,100,100,0,0,1,3,1,"
        f"{style.alignment},60,60,{style.margin_v},1\n"
        f"\n"
        f"[Events]\n"
        f"Format: Layer, Start, End, Style, Name, MarginL, MarginR, "
        f"MarginV, Effect, Text\n"
    )


def _segment_to_karaoke(segment: Segment) -> str:
    """Render one segment as a karaoke line with ``{\\kNNN}`` tags per word.

    The ``\\k`` duration is in **centiseconds** of *display* time — i.e.
    how long each word stays highlighted. We compute it from the word's
    end-start delta.
    """
    if not segment.words:
        return _escape_text(segment.text)
    parts: list[str] = []
    for w in segment.words:
        k_cs = max(1, int(round((w.end - w.start) * 100)))
        parts.append(f"{{\\k{k_cs}}}{_escape_text(w.word)}")
    return "".join(parts)


def build_ass(segments: list[Segment], style: AssStyle = AssStyle()) -> str:
    """Build a complete ASS document from aligned segments."""
    out = [_build_header(style)]
    for seg in segments:
        start = _fmt_timestamp(seg.start)
        end = _fmt_timestamp(seg.end)
        text = _segment_to_karaoke(seg)
        out.append(f"Dialogue: 0,{start},{end},Default,,0,0,0,,{text}\n")
    return "".join(out)


def write_ass(
    segments: list[Segment],
    output_path: Path,
    style: AssStyle = AssStyle(),
) -> Path:
    """Write the ASS file to disk and return the path."""
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_ass(segments, style), encoding="utf-8")
    return output_path


__all__ = [
    "AssStyle",
    "Segment",
    "WordTiming",
    "build_ass",
    "write_ass",
]
