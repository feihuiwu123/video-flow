"""End-to-end pipeline — the glue layer the CLI invokes.

Stage order (PRD §5 happy path, minus the review interrupts):
    parser → tts → subtitles → ffmpeg scenes → ffmpeg concat
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Optional

from videoflow.config import Config
from videoflow.ffmpeg_wrapper import (
    RenderSpec,
    compose_scene,
    concat_scenes,
    escape_filter_path,
    has_filter,
)
from videoflow.models import Project, ShotList
from videoflow.parser import parse_file
from videoflow.subtitles import AssStyle, write_ass
from videoflow.tts import EdgeTTSProvider, TTSProvider, synthesize_all

logger = logging.getLogger(__name__)


def _render_spec_from_config(cfg: Config) -> RenderSpec:
    # FFmpeg expects 0xRRGGBB, config stores #RRGGBB.
    bg = cfg.rendering.background_color.lstrip("#")
    return RenderSpec(
        width=cfg.rendering.width,
        height=cfg.rendering.height,
        fps=cfg.rendering.fps,
        background_color=f"0x{bg}",
        preset=cfg.ffmpeg.preset,
        crf=cfg.ffmpeg.crf,
        audio_bitrate=cfg.ffmpeg.audio_bitrate,
    )


def _ass_style_from_config(cfg: Config) -> AssStyle:
    return AssStyle(
        font_name=cfg.subtitles.font_name,
        font_size=cfg.subtitles.font_size,
        primary_color=cfg.subtitles.primary_color,
        outline_color=cfg.subtitles.outline_color,
        alignment=cfg.subtitles.alignment,
        margin_v=cfg.subtitles.margin_v,
    )


async def run_tts(
    shotlist: ShotList,
    audio_dir: Path,
    provider: TTSProvider,
) -> dict[str, float]:
    items = [
        (shot.shot_id, shot.narration, audio_dir / f"{shot.shot_id}.mp3")
        for shot in shotlist.shots
    ]
    durations = await synthesize_all(provider, items)
    for shot in shotlist.shots:
        shot.audio_file = audio_dir / f"{shot.shot_id}.mp3"
    return durations


def render_all_scenes(
    shotlist: ShotList,
    scenes_dir: Path,
    subtitle_path: Path,
    spec: RenderSpec,
) -> list[Path]:
    """Render one MP4 per shot. Subtitles are burned once per-shot so concat
    can use ``-c copy``. Each shot's subtitle offset matches its start time,
    so a single ASS file works across all shots.
    """
    scene_paths: list[Path] = []
    for shot in shotlist.shots:
        assert shot.audio_file is not None, "Run TTS before rendering scenes"
        out = scenes_dir / f"{shot.shot_id}.mp4"
        compose_scene(
            audio_path=shot.audio_file,
            output_path=out,
            duration=shot.duration,
            subtitle_path=None,  # Subtitles burned in the final concat pass.
            spec=spec,
        )
        scene_paths.append(out)
    return scene_paths


def finalize(
    scene_paths: list[Path],
    subtitle_path: Path,
    final_path: Path,
    spec: RenderSpec,
) -> Path:
    """Concat scenes; burn subtitles when the local ffmpeg supports it.

    Homebrew's default ffmpeg is built without libass, in which case we
    skip the burn pass, rename the concatenated raw file as the final
    MP4, and log a warning. The ``.ass`` file is still written to the
    project workspace so the user can mux subtitles externally.
    """
    concat_raw = final_path.parent / "_concat_raw.mp4"
    concat_scenes(scene_paths, concat_raw)

    if not has_filter("subtitles"):
        logger.warning(
            "ffmpeg was built without libass — skipping subtitle burn-in. "
            "ASS file is available at %s",
            subtitle_path,
        )
        concat_raw.replace(final_path)
        return final_path

    import subprocess

    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(concat_raw),
        "-vf",
        f"subtitles={escape_filter_path(subtitle_path)}",
        "-c:v",
        "libx264",
        "-preset",
        spec.preset,
        "-crf",
        str(spec.crf),
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "copy",
        "-movflags",
        "+faststart",
        str(final_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True, text=True)
    concat_raw.unlink(missing_ok=True)
    return final_path


def run_pipeline(
    input_path: Path,
    output_path: Path,
    config: Optional[Config] = None,
    provider: Optional[TTSProvider] = None,
    workspace_root: Optional[Path] = None,
) -> Project:
    """Blocking end-to-end run. Returns the finished Project record."""
    cfg = config or Config()
    workspace_root = workspace_root or cfg.runtime.workspace_root
    workspace_root.mkdir(parents=True, exist_ok=True)

    project = Project.new(workspace_root, input_path=input_path)
    logger.info("Project %s created at %s", project.project_id, project.workspace_dir)

    # 1. Parse.
    shotlist = parse_file(input_path)
    (project.workspace_dir / "shots_draft.json").write_text(
        shotlist.model_dump_json(indent=2), encoding="utf-8"
    )

    # 2. TTS (populates audio_file + real durations).
    tts_provider = provider or EdgeTTSProvider(
        voice=cfg.tts.voice, rate=cfg.tts.rate, pitch=cfg.tts.pitch
    )
    durations = asyncio.run(
        run_tts(shotlist, project.workspace_dir / "audio", tts_provider)
    )
    shotlist.retime_from_audio(durations)
    (project.workspace_dir / "shots.json").write_text(
        shotlist.model_dump_json(indent=2), encoding="utf-8"
    )

    # 3. Subtitles.
    subtitle_path = project.workspace_dir / "subtitles" / "final.ass"
    write_ass(shotlist, subtitle_path, _ass_style_from_config(cfg))

    # 4. Render scenes + finalize.
    spec = _render_spec_from_config(cfg)
    scene_paths = render_all_scenes(
        shotlist, project.workspace_dir / "scenes", subtitle_path, spec
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    finalize(scene_paths, subtitle_path, output_path, spec)

    project.shotlist = shotlist
    project.output_path = output_path
    project.status = project.status.__class__.DONE  # type: ignore[attr-defined]
    (project.workspace_dir / "project.json").write_text(
        json.dumps(
            {
                "project_id": project.project_id,
                "output_path": str(output_path),
                "actual_duration": shotlist.actual_duration,
                "num_shots": len(shotlist.shots),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return project
