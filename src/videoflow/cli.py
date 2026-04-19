"""``video-agent`` CLI entrypoint."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from videoflow.config import load_config
from videoflow.models import ShotList
from videoflow.parser import parse_file
from videoflow.pipeline import (
    finalize,
    render_all_scenes,
    run_pipeline,
    run_tts,
    _ass_style_from_config,
    _render_spec_from_config,
)
from videoflow.subtitles import write_ass
from videoflow.tts import EdgeTTSProvider

app = typer.Typer(
    add_completion=False,
    help="Videoflow — text-to-video pipeline (MVP demo).",
    no_args_is_help=True,
)
console = Console()


def _configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level.upper(), logging.INFO),
        format="%(asctime)s · %(name)s · %(levelname)s · %(message)s",
    )


@app.command()
def generate(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False, help="Markdown script."),
    output: Path = typer.Option(
        Path("workspace/demo.mp4"), "--output", "-o", help="Final MP4 path."
    ),
    config_path: Optional[Path] = typer.Option(
        Path("config.toml"),
        "--config",
        "-c",
        help="TOML config file (defaults to ./config.toml if present).",
    ),
    voice: Optional[str] = typer.Option(None, "--voice", help="Override TTS voice."),
) -> None:
    """End-to-end: Markdown → MP4."""
    cfg = load_config(config_path if config_path and config_path.exists() else None)
    if voice:
        cfg.tts.voice = voice
    _configure_logging(cfg.runtime.log_level)

    console.print(f"[bold cyan]Videoflow[/bold cyan] · generating from {input_path}")
    project = run_pipeline(input_path, output, config=cfg)
    console.print(f"[green]✓[/green] Project: {project.project_id}")
    console.print(f"[green]✓[/green] Output : {project.output_path}")
    if project.shotlist:
        console.print(
            f"[green]✓[/green] Shots  : {len(project.shotlist.shots)} · "
            f"duration {project.shotlist.actual_duration:.1f}s"
        )


@app.command()
def parse(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
) -> None:
    """Parse Markdown and print/save the ShotList as JSON."""
    shotlist = parse_file(input_path)
    payload = shotlist.model_dump_json(indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        console.print(f"[green]✓[/green] Wrote {output}")
    else:
        console.print(payload)

    table = Table(title=f"Shots ({len(shotlist.shots)})")
    table.add_column("ID")
    table.add_column("Duration (s)")
    table.add_column("Narration preview")
    for shot in shotlist.shots:
        preview = shot.narration[:40] + ("…" if len(shot.narration) > 40 else "")
        table.add_row(shot.shot_id, f"{shot.duration:.1f}", preview)
    console.print(table)


@app.command()
def tts(
    shots_json: Path = typer.Argument(..., exists=True, dir_okay=False),
    output_dir: Path = typer.Option(
        Path("workspace/audio"), "--output", "-o", help="Directory for MP3 files."
    ),
    voice: Optional[str] = typer.Option(None, "--voice"),
    config_path: Optional[Path] = typer.Option(Path("config.toml"), "--config", "-c"),
) -> None:
    """Generate per-shot MP3s from a shots.json file."""
    cfg = load_config(config_path if config_path and config_path.exists() else None)
    if voice:
        cfg.tts.voice = voice
    _configure_logging(cfg.runtime.log_level)

    shotlist = ShotList.model_validate_json(shots_json.read_text(encoding="utf-8"))
    provider = EdgeTTSProvider(voice=cfg.tts.voice, rate=cfg.tts.rate, pitch=cfg.tts.pitch)
    durations = asyncio.run(run_tts(shotlist, output_dir, provider))
    shotlist.retime_from_audio(durations)
    out_json = output_dir.parent / "shots.json"
    out_json.write_text(shotlist.model_dump_json(indent=2), encoding="utf-8")

    console.print(f"[green]✓[/green] Wrote {len(durations)} audio clips → {output_dir}")
    console.print(f"[green]✓[/green] Updated ShotList → {out_json}")


@app.command()
def render(
    project_dir: Path = typer.Argument(..., exists=True, file_okay=False),
    output: Path = typer.Option(Path("workspace/final.mp4"), "--output", "-o"),
    config_path: Optional[Path] = typer.Option(Path("config.toml"), "--config", "-c"),
) -> None:
    """Render scenes + finalize from a project directory containing shots.json."""
    cfg = load_config(config_path if config_path and config_path.exists() else None)
    _configure_logging(cfg.runtime.log_level)

    shots_json = project_dir / "shots.json"
    if not shots_json.exists():
        console.print(f"[red]✗[/red] Missing {shots_json}")
        sys.exit(1)
    shotlist = ShotList.model_validate_json(shots_json.read_text(encoding="utf-8"))

    # Attach audio files based on convention.
    audio_dir = project_dir / "audio"
    for shot in shotlist.shots:
        shot.audio_file = audio_dir / f"{shot.shot_id}.mp3"
        if not shot.audio_file.exists():
            console.print(f"[red]✗[/red] Missing audio {shot.audio_file}")
            sys.exit(1)

    subtitle_path = project_dir / "subtitles" / "final.ass"
    write_ass(shotlist, subtitle_path, _ass_style_from_config(cfg))

    spec = _render_spec_from_config(cfg)
    scene_paths = render_all_scenes(shotlist, project_dir / "scenes", subtitle_path, spec)
    output.parent.mkdir(parents=True, exist_ok=True)
    finalize(scene_paths, subtitle_path, output, spec)
    console.print(f"[green]✓[/green] Rendered → {output}")


@app.command()
def version() -> None:
    from videoflow import __version__

    console.print(f"videoflow {__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
