"""FFmpeg composition — pure command-line, no MoviePy dependency.

Matches PRD §A.5's recipe:
- Solid colour background held for the shot's duration.
- TTS audio mixed in.
- ASS subtitle file burned with ``-vf subtitles=``.
- Final concat with ``concat`` demuxer (copy codec for speed).
"""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class FFmpegError(RuntimeError):
    """Raised when an FFmpeg invocation exits non-zero."""


@dataclass(frozen=True)
class RenderSpec:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    background_color: str = "0x0A1929"  # Dark navy; matches Videoflow brand.
    preset: str = "medium"
    crf: int = 23
    audio_bitrate: str = "192k"


def _ensure_ffmpeg() -> None:
    if shutil.which("ffmpeg") is None:
        raise FFmpegError("ffmpeg not found on PATH — install FFmpeg 6+ first")


def has_filter(name: str) -> bool:
    """Check whether the installed ffmpeg exposes a specific filter.

    Many minimal ffmpeg builds (e.g. stock Homebrew macOS) omit libass, so
    the ``subtitles``/``ass`` filters are missing. We use this to degrade
    gracefully rather than fail the whole pipeline.
    """
    if shutil.which("ffmpeg") is None:
        return False
    try:
        out = subprocess.run(
            ["ffmpeg", "-hide_banner", "-filters"],
            capture_output=True,
            text=True,
            check=True,
        ).stdout
    except subprocess.CalledProcessError:
        return False
    for line in out.splitlines():
        # Format: " T.. filtername         types    description"
        parts = line.split()
        if len(parts) >= 2 and parts[1] == name:
            return True
    return False


def escape_filter_path(path: Path) -> str:
    """Escape a path for use inside an ffmpeg filter value.

    ffmpeg's filter-graph parser treats ``:`` as an option separator and
    ``,`` / ``'`` / ``\\`` as meta characters. When a filter argument is
    passed via a subprocess argv list (no shell), we must escape manually
    rather than relying on shell quoting.
    """
    raw = str(path.resolve())
    # Escape order matters: backslash first, then colon, then commas, then
    # single quotes. Result is a bare value (no surrounding quotes).
    return (
        raw.replace("\\", "\\\\")
        .replace(":", r"\:")
        .replace("'", r"\'")
        .replace(",", r"\,")
    )


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise FFmpegError(
            f"ffmpeg failed (exit {proc.returncode}):\nCMD: {' '.join(cmd)}\n"
            f"STDERR:\n{proc.stderr[-2000:]}"
        )


def compose_scene(
    audio_path: Path,
    output_path: Path,
    duration: float,
    visual_path: Path | None = None,
    subtitle_path: Path | None = None,
    spec: RenderSpec = RenderSpec(),
) -> Path:
    """Render one shot: static frame + audio + optional subtitles.

    Args:
        visual_path: PNG/JPG used as the video frame. If omitted, an lavfi
            ``color`` source of ``spec.background_color`` is used (legacy
            "plain colour" mode, useful for tests).
        subtitle_path: Optional ASS/SRT file. Silently ignored when the
            local ffmpeg lacks the ``subtitles`` filter (see ``has_filter``).
    """
    _ensure_ffmpeg()
    output_path.parent.mkdir(parents=True, exist_ok=True)

    vf_filters: list[str] = []
    inputs: list[str] = []
    if visual_path is not None:
        # Loop a still image for the duration of the shot, then scale/pad
        # to the target aspect so the output is always ``spec.width×height``.
        inputs += ["-loop", "1", "-t", f"{duration:.3f}", "-i", str(visual_path)]
        vf_filters.append(
            f"scale={spec.width}:{spec.height}:force_original_aspect_ratio=decrease"
        )
        vf_filters.append(
            f"pad={spec.width}:{spec.height}:(ow-iw)/2:(oh-ih)/2:color={spec.background_color}"
        )
    else:
        inputs += [
            "-f",
            "lavfi",
            "-i",
            f"color=c={spec.background_color}:s={spec.width}x{spec.height}:r={spec.fps}:d={duration:.3f}",
        ]

    vf_filters.append("format=yuv420p")
    if subtitle_path is not None and has_filter("subtitles"):
        vf_filters.insert(0, f"subtitles={escape_filter_path(subtitle_path)}")

    cmd = [
        "ffmpeg",
        "-y",
        *inputs,
        "-i",
        str(audio_path),
        "-vf",
        ",".join(vf_filters),
        "-r",
        str(spec.fps),
        "-c:v",
        "libx264",
        "-preset",
        spec.preset,
        "-crf",
        str(spec.crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-b:a",
        spec.audio_bitrate,
        "-shortest",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    _run(cmd)
    return output_path


def concat_scenes(scene_paths: list[Path], output_path: Path) -> Path:
    """Concatenate pre-rendered scene MP4s using the concat demuxer.

    All inputs must share identical codec/resolution/fps (they do if produced
    by :func:`compose_scene`), which lets us use ``-c copy`` — instantaneous.
    """
    _ensure_ffmpeg()
    if not scene_paths:
        raise ValueError("concat_scenes called with empty scene_paths")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    list_file = output_path.parent / f".{output_path.stem}.concat.txt"
    list_file.write_text(
        "\n".join(f"file '{p.resolve()}'" for p in scene_paths) + "\n",
        encoding="utf-8",
    )
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        "-movflags",
        "+faststart",
        str(output_path),
    ]
    try:
        _run(cmd)
    finally:
        list_file.unlink(missing_ok=True)
    return output_path
