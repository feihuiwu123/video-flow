"""End-to-end pipeline — the glue layer the CLI invokes.

Stage order (PRD §5 happy path, minus the review interrupts):
    parser → tts → subtitles → ffmpeg scenes → ffmpeg concat

State hooks
-----------
Stages optionally emit events to a SQLite event log (see ``videoflow.state``).
Callers pass a ``db_path`` — if omitted, the pipeline runs without touching
the DB (this keeps the demo path and unit tests free of SQLite).
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
from typing import Any, Optional

from videoflow import state
from videoflow.cache import CacheKey, CacheStore
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
from videoflow.renderer import render_visual
from videoflow.subtitles import AssStyle, write_ass, write_ass_with_align
from videoflow.tts import EdgeTTSProvider, TTSProvider, synthesize_all

logger = logging.getLogger(__name__)


def _emit(
    db_path: Optional[Path],
    project_id: str,
    stage: str,
    status: str,
    payload: Optional[dict[str, Any]] = None,
) -> None:
    """Fire-and-forget event recorder. No-op when ``db_path`` is None."""
    if db_path is None:
        return
    try:
        state.record_event(
            db_path, project_id=project_id, stage=stage, status=status, payload=payload
        )
    except Exception:  # pragma: no cover — observability must not kill the run.
        logger.exception("Failed to record event %s/%s/%s", project_id, stage, status)


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
    *,
    max_concurrency: int = 4,
    cache: Optional[CacheStore] = None,
    cache_params: Optional[dict[str, str]] = None,
) -> dict[str, float]:
    items = [
        (shot.shot_id, shot.narration, audio_dir / f"{shot.shot_id}.mp3")
        for shot in shotlist.shots
    ]
    durations = await synthesize_all(
        provider,
        items,
        max_concurrency=max_concurrency,
        cache=cache,
        cache_params=cache_params,
    )
    for shot in shotlist.shots:
        shot.audio_file = audio_dir / f"{shot.shot_id}.mp3"
    return durations


def render_all_visuals(
    shotlist: ShotList,
    visuals_dir: Path,
    spec: RenderSpec,
    *,
    max_concurrency: int = 4,
    cache: Optional[CacheStore] = None,
) -> None:
    """Rasterise each shot's TitleCardVisual to a PNG — parallel over shots.

    PNGs live at ``visuals_dir/<shot_id>.png`` and are attached to the
    corresponding shot via ``shot.visual_file``. When a :class:`CacheStore`
    is supplied we look up a (shot_id + visual repr + dimensions) hash
    before calling Pillow; cache misses populate the cache on completion.
    """
    import concurrent.futures

    visuals_dir.mkdir(parents=True, exist_ok=True)

    def _render_one(shot) -> None:
        out = visuals_dir / f"{shot.shot_id}.png"

        if cache is not None:
            key = CacheKey.from_visual(
                shot_id=shot.shot_id,
                visual_repr=shot.visual.model_dump_json(),
                width=spec.width,
                height=spec.height,
                background_color=spec.background_color,
            )
            hit = cache.get(key, kind="visual", ext="png")
            if hit is not None:
                import shutil as _sh
                _sh.copy2(hit, out)
                shot.visual_file = out
                return

        render_visual(
            shot,
            out,
            width=spec.width,
            height=spec.height,
            background_color=spec.background_color.replace("0x", "#"),
        )
        shot.visual_file = out

        if cache is not None:
            key = CacheKey.from_visual(
                shot_id=shot.shot_id,
                visual_repr=shot.visual.model_dump_json(),
                width=spec.width,
                height=spec.height,
                background_color=spec.background_color,
            )
            cache.put(key, out, kind="visual", ext="png", move=False)

    if max_concurrency <= 1 or len(shotlist.shots) <= 1:
        for shot in shotlist.shots:
            _render_one(shot)
        return

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as pool:
        list(pool.map(_render_one, shotlist.shots))


def render_all_scenes(
    shotlist: ShotList,
    scenes_dir: Path,
    subtitle_path: Path,
    spec: RenderSpec,
    *,
    max_concurrency: int = 2,
) -> list[Path]:
    """Render one MP4 per shot — parallel subprocess invocations of FFmpeg.

    Subtitles are burned in the final concat pass only (to keep ``-c copy``
    viable here); they are silently skipped if libass is unavailable.

    FFmpeg itself is multithreaded, so we cap concurrency modestly to
    avoid over-subscribing CPU cores.
    """
    import concurrent.futures

    scenes_dir.mkdir(parents=True, exist_ok=True)

    def _compose_one(shot) -> Path:
        assert shot.audio_file is not None, "Run TTS before rendering scenes"
        assert shot.visual_file is not None, "Render visuals before rendering scenes"
        out = scenes_dir / f"{shot.shot_id}.mp4"
        compose_scene(
            audio_path=shot.audio_file,
            output_path=out,
            duration=shot.duration,
            visual_path=shot.visual_file,
            subtitle_path=None,
            spec=spec,
        )
        return out

    if max_concurrency <= 1 or len(shotlist.shots) <= 1:
        return [_compose_one(shot) for shot in shotlist.shots]

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_concurrency) as pool:
        # Preserve the input order so concat_scenes gets ``S01`` before ``S02``.
        return list(pool.map(_compose_one, shotlist.shots))


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


def _cache_store_from_config(cfg: Config, workspace_root: Path) -> Optional[CacheStore]:
    """Materialise a :class:`CacheStore` if enabled in config; else ``None``.

    Relative directories resolve against ``workspace_root`` so every project
    under the same workspace shares one cache. Absolute paths pass through.
    """
    if not cfg.cache.enabled:
        return None
    directory = Path(cfg.cache.directory)
    if not directory.is_absolute():
        directory = workspace_root / directory
    return CacheStore(directory)


def _write_project_summary(project: Project, output_path: Path, shotlist: ShotList) -> None:
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


def run_pipeline(
    input_path: Path,
    output_path: Path,
    config: Optional[Config] = None,
    provider: Optional[TTSProvider] = None,
    workspace_root: Optional[Path] = None,
    db_path: Optional[Path] = None,
    pre_parsed_shotlist: Optional[ShotList] = None,
) -> Project:
    """Blocking end-to-end run. Returns the finished Project record.

    When ``db_path`` is given, the project is indexed into SQLite and each
    stage emits ``started`` / ``done`` / ``failed`` events. Pass ``None``
    (the default) to run without persistence — useful for tests.

    Args:
        pre_parsed_shotlist: If provided, skip parsing stage and use this shotlist.
            Useful when CLI has already parsed with LLM and wants to confirm before pipeline.
    """
    cfg = config or Config()
    workspace_root = workspace_root or cfg.runtime.workspace_root
    workspace_root.mkdir(parents=True, exist_ok=True)

    cache = _cache_store_from_config(cfg, workspace_root)
    project = Project.new(workspace_root, input_path=input_path)
    logger.info("Project %s created at %s", project.project_id, project.workspace_dir)

    if db_path is not None:
        state.init_db(db_path)
        state.upsert_project(
            db_path,
            project_id=project.project_id,
            workspace_dir=project.workspace_dir,
            input_path=input_path,
            output_path=output_path,
            status="created",
        )

    pid = project.project_id

    try:
        # 1. Parse (skip if pre-parsed shotlist provided from CLI)
        if pre_parsed_shotlist is not None:
            shotlist = pre_parsed_shotlist
            # Write both draft and final since we're skipping parse stage
            (project.workspace_dir / "shots_draft.json").write_text(
                shotlist.model_dump_json(indent=2), encoding="utf-8"
            )
            (project.workspace_dir / "shots.json").write_text(
                shotlist.model_dump_json(indent=2), encoding="utf-8"
            )
            logger.info("Using pre-parsed shotlist: %d shots", len(shotlist.shots))
            if db_path is not None:
                state.upsert_project(
                    db_path,
                    project_id=pid,
                    workspace_dir=project.workspace_dir,
                    status="parsed",
                    num_shots=len(shotlist.shots),
                )
        else:
            _emit(db_path, pid, state.STAGE_PARSE, state.STATUS_STARTED)
            shotlist = parse_file(input_path)
            (project.workspace_dir / "shots_draft.json").write_text(
                shotlist.model_dump_json(indent=2), encoding="utf-8"
            )
            _emit(
                db_path,
                pid,
                state.STAGE_PARSE,
                state.STATUS_DONE,
                {"num_shots": len(shotlist.shots)},
            )
            if db_path is not None:
                state.upsert_project(
                    db_path,
                    project_id=pid,
                    workspace_dir=project.workspace_dir,
                    status="parsed",
                    num_shots=len(shotlist.shots),
                )

        # 2. TTS (populates audio_file + real durations).
        _emit(db_path, pid, state.STAGE_TTS, state.STATUS_STARTED)
        tts_provider = provider or EdgeTTSProvider(
            voice=cfg.tts.voice, rate=cfg.tts.rate, pitch=cfg.tts.pitch
        )
        tts_cache_params = (
            {"voice": cfg.tts.voice, "rate": cfg.tts.rate, "pitch": cfg.tts.pitch}
            if cache is not None
            else None
        )
        durations = asyncio.run(
            run_tts(
                shotlist,
                project.workspace_dir / "audio",
                tts_provider,
                max_concurrency=cfg.performance.tts_concurrency,
                cache=cache,
                cache_params=tts_cache_params,
            )
        )
        shotlist.retime_from_audio(durations)
        (project.workspace_dir / "shots.json").write_text(
            shotlist.model_dump_json(indent=2), encoding="utf-8"
        )
        _emit(
            db_path,
            pid,
            state.STAGE_TTS,
            state.STATUS_DONE,
            {"actual_duration": shotlist.actual_duration},
        )
        if db_path is not None:
            state.upsert_project(
                db_path,
                project_id=pid,
                workspace_dir=project.workspace_dir,
                status="tts_done",
                actual_duration=shotlist.actual_duration,
            )

        # 3. Visuals.
        _emit(db_path, pid, state.STAGE_RENDER_VISUALS, state.STATUS_STARTED)
        spec = _render_spec_from_config(cfg)
        render_all_visuals(
            shotlist,
            project.workspace_dir / "visuals",
            spec,
            max_concurrency=cfg.performance.visuals_concurrency,
            cache=cache,
        )
        _emit(db_path, pid, state.STAGE_RENDER_VISUALS, state.STATUS_DONE)

        # 4. Subtitles.
        _emit(db_path, pid, state.STAGE_SUBTITLES, state.STATUS_STARTED)
        subtitle_path = project.workspace_dir / "subtitles" / "final.ass"
        if cfg.align.provider == "mcp":
            logger.info("Using align MCP for word-level subtitles")
            write_ass_with_align(
                shotlist,
                subtitle_path,
                _ass_style_from_config(cfg),
                language=cfg.align.language,
            )
        else:
            write_ass(shotlist, subtitle_path, _ass_style_from_config(cfg))
        _emit(db_path, pid, state.STAGE_SUBTITLES, state.STATUS_DONE)

        # 5. Scenes.
        _emit(db_path, pid, state.STAGE_RENDER_SCENES, state.STATUS_STARTED)
        scene_paths = render_all_scenes(
            shotlist,
            project.workspace_dir / "scenes",
            subtitle_path,
            spec,
            max_concurrency=cfg.performance.scenes_concurrency,
        )
        _emit(db_path, pid, state.STAGE_RENDER_SCENES, state.STATUS_DONE)

        # 6. Finalize.
        _emit(db_path, pid, state.STAGE_FINALIZE, state.STATUS_STARTED)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        finalize(scene_paths, subtitle_path, output_path, spec)
        _emit(
            db_path,
            pid,
            state.STAGE_FINALIZE,
            state.STATUS_DONE,
            {"output_path": str(output_path)},
        )
    except Exception as exc:  # noqa: BLE001 — log-and-rethrow
        _emit(db_path, pid, "pipeline", state.STATUS_FAILED, {"error": str(exc)})
        if db_path is not None:
            state.upsert_project(
                db_path,
                project_id=pid,
                workspace_dir=project.workspace_dir,
                status="failed",
            )
        raise

    project.shotlist = shotlist
    project.output_path = output_path
    project.status = project.status.__class__.DONE  # type: ignore[attr-defined]
    _write_project_summary(project, output_path, shotlist)
    if db_path is not None:
        state.upsert_project(
            db_path,
            project_id=pid,
            workspace_dir=project.workspace_dir,
            output_path=output_path,
            status="done",
            actual_duration=shotlist.actual_duration,
        )
    return project


def resume_project(
    project_dir: Path,
    output_path: Optional[Path] = None,
    config: Optional[Config] = None,
    provider: Optional[TTSProvider] = None,
    db_path: Optional[Path] = None,
) -> Project:
    """Idempotently re-run only the stages that haven't produced artifacts.

    Filesystem is the truth source: we consult :func:`state.stage_readiness`
    and run each missing stage in order. Already-done stages are skipped.
    Useful for (a) recovering from crashes, (b) picking up after a manual
    edit to ``shots.json``.
    """
    cfg = config or Config()
    project_dir = Path(project_dir)
    if not project_dir.exists():
        raise FileNotFoundError(project_dir)

    # Resume inherits the cache from config just like a fresh run would.
    cache = _cache_store_from_config(cfg, project_dir.parent)

    # Reconstruct a Project handle from the workspace.
    pid = project_dir.name
    if not pid.startswith("proj_"):
        raise ValueError(f"{project_dir} is not a Videoflow project workspace")
    project = Project(project_id=pid, workspace_dir=project_dir)

    # Source shotlist: prefer the retimed shots.json if it exists.
    shots_json = project_dir / "shots.json"
    shots_draft = project_dir / "shots_draft.json"
    source = shots_json if shots_json.exists() else shots_draft
    if not source.exists():
        raise FileNotFoundError(
            f"Neither shots.json nor shots_draft.json found in {project_dir}"
        )
    shotlist = ShotList.model_validate_json(source.read_text(encoding="utf-8"))

    # Re-attach paths by convention.
    audio_dir = project_dir / "audio"
    visuals_dir = project_dir / "visuals"
    for shot in shotlist.shots:
        audio = audio_dir / f"{shot.shot_id}.mp3"
        if audio.exists():
            shot.audio_file = audio
        visual = visuals_dir / f"{shot.shot_id}.png"
        if visual.exists():
            shot.visual_file = visual

    spec = _render_spec_from_config(cfg)
    subtitle_path = project_dir / "subtitles" / "final.ass"
    resolved_output = output_path or (project_dir / "final.mp4")

    readiness = state.stage_readiness(project_dir)
    logger.info("Resume %s · readiness=%s", pid, readiness)

    try:
        # TTS (skip if all audio files present).
        if not readiness[state.STAGE_TTS]:
            _emit(db_path, pid, state.STAGE_TTS, state.STATUS_STARTED, {"resume": True})
            tts_provider = provider or EdgeTTSProvider(
                voice=cfg.tts.voice, rate=cfg.tts.rate, pitch=cfg.tts.pitch
            )
            tts_cache_params = (
                {"voice": cfg.tts.voice, "rate": cfg.tts.rate, "pitch": cfg.tts.pitch}
                if cache is not None
                else None
            )
            durations = asyncio.run(
                run_tts(
                    shotlist,
                    audio_dir,
                    tts_provider,
                    max_concurrency=cfg.performance.tts_concurrency,
                    cache=cache,
                    cache_params=tts_cache_params,
                )
            )
            shotlist.retime_from_audio(durations)
            shots_json.write_text(shotlist.model_dump_json(indent=2), encoding="utf-8")
            _emit(db_path, pid, state.STAGE_TTS, state.STATUS_DONE)

        # Visuals.
        if not readiness[state.STAGE_RENDER_VISUALS]:
            _emit(
                db_path, pid, state.STAGE_RENDER_VISUALS, state.STATUS_STARTED, {"resume": True}
            )
            render_all_visuals(
                shotlist,
                visuals_dir,
                spec,
                max_concurrency=cfg.performance.visuals_concurrency,
                cache=cache,
            )
            _emit(db_path, pid, state.STAGE_RENDER_VISUALS, state.STATUS_DONE)

        # Subtitles.
        if not readiness[state.STAGE_SUBTITLES]:
            _emit(
                db_path, pid, state.STAGE_SUBTITLES, state.STATUS_STARTED, {"resume": True}
            )
            if cfg.align.provider == "mcp":
                logger.info("Using align MCP for word-level subtitles")
                write_ass_with_align(
                    shotlist,
                    subtitle_path,
                    _ass_style_from_config(cfg),
                    language=cfg.align.language,
                )
            else:
                write_ass(shotlist, subtitle_path, _ass_style_from_config(cfg))
            _emit(db_path, pid, state.STAGE_SUBTITLES, state.STATUS_DONE)

        # Scenes.
        if not readiness[state.STAGE_RENDER_SCENES]:
            _emit(
                db_path,
                pid,
                state.STAGE_RENDER_SCENES,
                state.STATUS_STARTED,
                {"resume": True},
            )
            # Ensure audio + visuals are attached before composing.
            for shot in shotlist.shots:
                if shot.audio_file is None:
                    shot.audio_file = audio_dir / f"{shot.shot_id}.mp3"
                if shot.visual_file is None:
                    shot.visual_file = visuals_dir / f"{shot.shot_id}.png"
            render_all_scenes(
                shotlist,
                project_dir / "scenes",
                subtitle_path,
                spec,
                max_concurrency=cfg.performance.scenes_concurrency,
            )
            _emit(db_path, pid, state.STAGE_RENDER_SCENES, state.STATUS_DONE)

        # Finalize.
        if not readiness[state.STAGE_FINALIZE]:
            _emit(
                db_path, pid, state.STAGE_FINALIZE, state.STATUS_STARTED, {"resume": True}
            )
            resolved_output.parent.mkdir(parents=True, exist_ok=True)
            scene_paths = [
                project_dir / "scenes" / f"{s.shot_id}.mp4" for s in shotlist.shots
            ]
            finalize(scene_paths, subtitle_path, resolved_output, spec)
            _emit(
                db_path,
                pid,
                state.STAGE_FINALIZE,
                state.STATUS_DONE,
                {"output_path": str(resolved_output)},
            )
    except Exception as exc:  # noqa: BLE001
        _emit(db_path, pid, "pipeline", state.STATUS_FAILED, {"error": str(exc), "resume": True})
        if db_path is not None:
            state.upsert_project(
                db_path, project_id=pid, workspace_dir=project_dir, status="failed"
            )
        raise

    project.shotlist = shotlist
    project.output_path = resolved_output
    project.status = project.status.__class__.DONE  # type: ignore[attr-defined]
    _write_project_summary(project, resolved_output, shotlist)
    if db_path is not None:
        state.upsert_project(
            db_path,
            project_id=pid,
            workspace_dir=project_dir,
            output_path=resolved_output,
            status="done",
            num_shots=len(shotlist.shots),
            actual_duration=shotlist.actual_duration,
        )
    return project
