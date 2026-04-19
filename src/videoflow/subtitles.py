"""ASS subtitle generation.

The PRD specifies Paraformer word-level forced alignment. The demo uses the
simpler "one subtitle event per shot" approach — each subtitle runs for the
duration of the matching audio clip. Good enough for the happy-path demo;
the Provider boundary (``SubtitleBuilder``) is stable so a Paraformer-based
implementation can slot in later.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from videoflow.models import ShotList


@dataclass(frozen=True)
class AssStyle:
    """ASS style knobs — the subset we actually emit."""

    font_name: str = "PingFang SC"
    font_size: int = 56
    primary_color: str = "&H00FFFFFF"
    outline_color: str = "&H00000000"
    alignment: int = 2  # Bottom center.
    margin_v: int = 200


def _fmt_timestamp(seconds: float) -> str:
    """Render seconds as ASS H:MM:SS.cs (centisecond precision)."""
    if seconds < 0:
        seconds = 0
    hours = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    cs = int(round((seconds - int(seconds)) * 100))
    if cs == 100:  # Guard rounding overflow.
        secs += 1
        cs = 0
    return f"{hours}:{mins:02d}:{secs:02d}.{cs:02d}"


def _escape_text(text: str) -> str:
    # ASS uses {...} for override tags; escape braces and commas.
    return text.replace("{", "(").replace("}", ")").replace("\n", " ")


def build_ass(shotlist: ShotList, style: AssStyle = AssStyle()) -> str:
    """Produce ASS v4.00+ content (returned as a string)."""
    header = [
        "[Script Info]",
        "Title: Videoflow Demo Subtitles",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        (
            f"Style: Default,{style.font_name},{style.font_size},"
            f"{style.primary_color},{style.outline_color},&H64000000,"
            "0,0,0,0,100,100,0,0,1,3,1,"
            f"{style.alignment},80,80,{style.margin_v},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    events: list[str] = []
    for shot in shotlist.shots:
        events.append(
            "Dialogue: 0,"
            f"{_fmt_timestamp(shot.start)},{_fmt_timestamp(shot.end)},"
            f"Default,,0,0,0,,{_escape_text(shot.narration)}"
        )
    return "\n".join(header + events) + "\n"


def write_ass(shotlist: ShotList, output_path: Path, style: AssStyle = AssStyle()) -> Path:
    """Write the ASS file to ``output_path`` and return the path."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_ass(shotlist, style), encoding="utf-8")
    return output_path
