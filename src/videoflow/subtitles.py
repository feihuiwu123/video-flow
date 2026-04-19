"""ASS subtitle generation.

The PRD specifies Paraformer word-level forced alignment. The demo uses the
simpler "one subtitle event per shot" approach — each subtitle runs for the
duration of the matching audio clip. Good enough for the happy-path demo;
the Provider boundary (``SubtitleBuilder``) is stable so a Paraformer-based
implementation can slot in later.

For word-level alignment (karaoke-style highlighting), set ``align.provider``
to ``"mcp"`` in config.toml and ensure ``videoflow-align`` is installed.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from videoflow.models import ShotList

_LOGGER = logging.getLogger(__name__)


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
    """Produce ASS v4.00+ content (returned as a string).

    Uses per-shot timing (shot.start / shot.end) rather than word-level
    alignment. For word-level karaoke subtitles, use
    :func:`write_ass_with_align` instead.
    """
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


def write_ass(
    shotlist: ShotList,
    output_path: Path,
    style: AssStyle = AssStyle(),
) -> Path:
    """Write the ASS file to ``output_path`` and return the path.

    Uses per-shot timing. For word-level alignment via faster-whisper,
    use :func:`write_ass_with_align` instead.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_ass(shotlist, style), encoding="utf-8")
    return output_path


def _ass_header_with_karaoke_style(style: AssStyle) -> list[str]:
    """Return header lines for a word-level ASS file (karaoke-ready style)."""
    return [
        "[Script Info]",
        "Title: Videoflow (Word-Level Alignment)",
        "ScriptType: v4.00+",
        "PlayResX: 1080",
        "PlayResY: 1920",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, "
        "OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, "
        "ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        (
            f"Style: Default,{style.font_name},{style.font_size},"
            f"{style.primary_color},&H0000FFFF,"  # Secondary=yellow for karaoke
            f"{style.outline_color},&H64000000,"
            "0,0,0,0,100,100,0,0,1,3,1,"
            f"{style.alignment},80,80,{style.margin_v},1"
        ),
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]


async def _align_and_collect_lines(
    shotlist: ShotList,
    output_path: Path,
    language: str,
) -> list[str]:
    """Async worker: call the align MCP once per shot, return collected Dialogue lines."""
    from videoflow.mcp_align_client import AlignMCPClient

    client = AlignMCPClient()
    dialogue_lines: list[str] = []

    for shot in shotlist.shots:
        if shot.audio_file is None:
            _LOGGER.warning("Shot %s has no audio_file — skipping align", shot.shot_id)
            dialogue_lines.append(
                f"Dialogue: 0,{_fmt_timestamp(shot.start)},{_fmt_timestamp(shot.end)},"
                f"Default,,0,0,0,,{_escape_text(shot.narration)}"
            )
            continue

        temp_ass = output_path.parent / f"_{shot.shot_id}_aligned.ass"
        try:
            result = await client.align_subtitle(
                audio_path=shot.audio_file,
                text=shot.narration,
                output_ass=temp_ass,
                language=language,
                word_timestamps=True,
            )
            if temp_ass.exists():
                content = temp_ass.read_text(encoding="utf-8")
                for line in content.split("\n"):
                    if line.startswith("Dialogue:"):
                        dialogue_lines.append(line)
                temp_ass.unlink(missing_ok=True)
            _LOGGER.debug(
                "Aligned shot %s: %d words, %.2fs",
                shot.shot_id,
                result.num_words,
                result.duration,
            )
        except Exception as e:  # noqa: BLE001 — per-shot fallback is the whole point
            _LOGGER.warning(
                "Alignment failed for shot %s: %s — using shot timing",
                shot.shot_id,
                e,
            )
            dialogue_lines.append(
                f"Dialogue: 0,{_fmt_timestamp(shot.start)},{_fmt_timestamp(shot.end)},"
                f"Default,,0,0,0,,{_escape_text(shot.narration)}"
            )

    return dialogue_lines


def write_ass_with_align(
    shotlist: ShotList,
    output_path: Path,
    style: AssStyle = AssStyle(),
    language: str = "auto",
) -> Optional[Path]:
    """Write ASS subtitles with word-level alignment via the align MCP server.

    This function calls the ``videoflow-align`` MCP server for each shot to
    generate word-level karaoke timing. Falls back to standard per-shot ASS
    if the MCP server is unavailable.

    Args:
        shotlist: The shot list with narration and audio files attached.
        output_path: Where to write the final ASS file.
        style: ASS style configuration.
        language: ISO code for faster-whisper (e.g., "zh", "en") or "auto".

    Returns:
        Path to the output ASS file, or None if alignment failed.

    Note:
        Requires ``videoflow-align`` MCP server installed:
        ``pip install -e ./mcp_servers/align``
    """
    try:
        from videoflow.mcp_align_client import AlignMCPClient
    except ImportError:
        _LOGGER.warning(
            "videoflow-align not installed — falling back to per-shot ASS. "
            "Install with: pip install -e ./mcp_servers/align"
        )
        return write_ass(shotlist, output_path, style)

    try:
        client = AlignMCPClient()
        if not client.is_available():
            _LOGGER.warning(
                "videoflow-align not available — falling back to per-shot ASS"
            )
            return write_ass(shotlist, output_path, style)

        _LOGGER.info("Using align MCP for word-level subtitles")
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Run the async alignment loop. Detect if we're already inside a
        # running loop (e.g. called from LangGraph) and schedule accordingly.
        try:
            running = asyncio.get_running_loop()
        except RuntimeError:
            running = None

        if running is None:
            dialogue_lines = asyncio.run(
                _align_and_collect_lines(shotlist, output_path, language)
            )
        else:
            # We're inside an async context. Hand off to a worker thread so
            # we can still block for a sync return without nesting loops.
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                fut = pool.submit(
                    asyncio.run,
                    _align_and_collect_lines(shotlist, output_path, language),
                )
                dialogue_lines = fut.result()

        all_lines = _ass_header_with_karaoke_style(style) + dialogue_lines
        output_path.write_text("\n".join(all_lines) + "\n", encoding="utf-8")
        return output_path

    except Exception:  # noqa: BLE001 — last-ditch fallback preserves pipeline
        _LOGGER.exception("Align MCP error — falling back to per-shot ASS")
        return write_ass(shotlist, output_path, style)
