"""``video-agent`` CLI entrypoint."""

from __future__ import annotations

import asyncio
import json
import logging
import shutil
import sys
from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from videoflow import state
from videoflow.config import Config, load_config
from videoflow.models import ShotList
from videoflow.parser import parse_file
from videoflow.pipeline import (
    finalize,
    render_all_scenes,
    render_all_visuals,
    resume_project,
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


def _resolve_db_path(cfg: Config) -> Path:
    """Canonical DB location: ``<workspace_root>/videoflow.db``."""
    return state.default_db_path(cfg.runtime.workspace_root)


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
    no_track: bool = typer.Option(
        False, "--no-track", help="Skip SQLite event tracking for this run."
    ),
) -> None:
    """End-to-end: Markdown → MP4."""
    cfg = load_config(config_path if config_path and config_path.exists() else None)
    if voice:
        cfg.tts.voice = voice
    _configure_logging(cfg.runtime.log_level)

    db_path = None if no_track else _resolve_db_path(cfg)

    console.print(f"[bold cyan]Videoflow[/bold cyan] · generating from {input_path}")
    project = run_pipeline(input_path, output, config=cfg, db_path=db_path)
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
def llm(
    input_path: Path = typer.Argument(..., exists=True, dir_okay=False),
    output: Optional[Path] = typer.Option(None, "--output", "-o"),
    provider: str = typer.Option("deepseek", "--provider", "-p", help="LLM provider: deepseek, openai, anthropic"),
    template: Optional[str] = typer.Option(None, "--template", "-t", help="Template name: explainer, news_digest, story, tutorial"),
    config_path: Optional[Path] = typer.Option(Path("config.toml"), "--config", "-c"),
) -> None:
    """Parse Markdown using LLM (DeepSeek/OpenAI/Anthropic).

    Requires API key set in environment:
        export DEEPSEEK_API_KEY=sk-xxx  (recommended)
        export OPENAI_API_KEY=sk-xxx
        export ANTHROPIC_API_KEY=sk-ant-xxx
    """
    from videoflow.providers import get_llm_provider
    from videoflow.providers.llm_parser import parse_file as llm_parse_file
    from videoflow.templates import get_template

    cfg = load_config(config_path if config_path and config_path.exists() else None)

    # Get template if specified
    template_obj = None
    if template:
        template_obj = get_template(template)
        if template_obj:
            template_str = template_obj.get_system_prompt()
        else:
            console.print(f"[yellow]⚠[/yellow] Template '{template}' not found, using default")
            template_str = None
    else:
        template_str = None

    # Check provider availability
    llm_provider = get_llm_provider(provider)
    if llm_provider is None:
        available = get_llm_provider(None)  # Auto-detect
        if available:
            provider = available.name
            llm_provider = available
        else:
            console.print("[red]✗[/red] No LLM provider available.")
            console.print("Set one of: DEEPSEEK_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY")
            sys.exit(1)

    console.print(f"[cyan]Using LLM provider:[/cyan] {llm_provider.name}")

    try:
        shotlist = llm_parse_file(input_path, provider, template_str)
    except Exception as e:
        console.print(f"[red]✗[/red] LLM parsing failed: {e}")
        sys.exit(1)

    payload = shotlist.model_dump_json(indent=2)
    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(payload, encoding="utf-8")
        console.print(f"[green]✓[/green] Wrote {output}")
    else:
        console.print(payload)

    table = Table(title=f"LLM Shots ({len(shotlist.shots)})")
    table.add_column("ID")
    table.add_column("Duration (s)")
    table.add_column("Narration preview")
    for shot in shotlist.shots:
        preview = shot.narration[:50] + ("…" if len(shot.narration) > 50 else "")
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
    render_all_visuals(shotlist, project_dir / "visuals", spec)
    scene_paths = render_all_scenes(shotlist, project_dir / "scenes", subtitle_path, spec)
    output.parent.mkdir(parents=True, exist_ok=True)
    finalize(scene_paths, subtitle_path, output, spec)
    console.print(f"[green]✓[/green] Rendered → {output}")


@app.command()
def align(
    shots_json: Path = typer.Argument(..., exists=True, dir_okay=False),
    output_ass: Path = typer.Option(..., "--output", "-o", help="Output ASS file path."),
    language: str = typer.Option("auto", "--language", "-l", help="ISO code or 'auto'."),
    model_size: str = typer.Option(
        "base",
        "--model",
        "-m",
        help="faster-whisper model size: tiny, base, small, medium, large-v2.",
    ),
    config_path: Optional[Path] = typer.Option(Path("config.toml"), "--config", "-c"),
) -> None:
    """Generate word-level karaoke ASS subtitles using the align MCP server.

    Requires videoflow-align MCP installed:
        pip install -e ./mcp_servers/align
    """
    try:
        from videoflow.mcp_align_client import AlignMCPClient, AlignMCPUnavailable

        cfg = load_config(config_path if config_path and config_path.exists() else None)
        client = AlignMCPClient(config=cfg.align)

        if not client.is_available():
            console.print(
                "[red]✗[/red] videoflow-align not found. "
                "Install with: pip install -e ./mcp_servers/align"
            )
            raise typer.Exit(code=1)

        console.print(f"[bold cyan]videoflow[/bold cyan] · aligning {shots_json}")

        # Load shotlist and attach audio files
        shotlist = ShotList.model_validate_json(shots_json.read_text(encoding="utf-8"))
        audio_dir = shots_json.parent / "audio"

        for shot in shotlist.shots:
            shot.audio_file = audio_dir / f"{shot.shot_id}.mp3"

        # Generate aligned subtitles
        from videoflow.subtitles import write_ass_with_align

        result = write_ass_with_align(
            shotlist,
            output_ass,
            _ass_style_from_config(cfg),
            language=language,
        )

        if result is None:
            console.print("[red]✗[/red] Alignment failed")
            raise typer.Exit(code=1)

        console.print(f"[green]✓[/green] Word-level ASS → {output_ass}")

    except AlignMCPUnavailable as e:
        console.print(f"[red]✗[/red] {e}")
        raise typer.Exit(code=1)
    except ImportError:
        console.print(
            "[red]✗[/red] mcp_align_client not available. "
            "Ensure videoflow is installed correctly."
        )
        raise typer.Exit(code=1)


# ---------------------------------------------------------------------------
# M3.1 state & orchestration subcommands
# ---------------------------------------------------------------------------


@app.command("init-db")
def init_db_cmd(
    config_path: Optional[Path] = typer.Option(Path("config.toml"), "--config", "-c"),
    db: Optional[Path] = typer.Option(None, "--db", help="Override DB path."),
) -> None:
    """Create the state DB schema (idempotent)."""
    cfg = load_config(config_path if config_path and config_path.exists() else None)
    db_path = db or _resolve_db_path(cfg)
    state.init_db(db_path)
    console.print(f"[green]✓[/green] DB ready at {db_path}")


@app.command("list")
def list_cmd(
    status_filter: Optional[str] = typer.Option(
        None, "--status", "-s", help="Filter by status (created/parsed/tts_done/rendered/done/failed)."
    ),
    limit: int = typer.Option(50, "--limit", "-n"),
    config_path: Optional[Path] = typer.Option(Path("config.toml"), "--config", "-c"),
    db: Optional[Path] = typer.Option(None, "--db"),
    json_out: bool = typer.Option(False, "--json", help="Emit JSON instead of a table."),
) -> None:
    """List known projects, most recent first."""
    cfg = load_config(config_path if config_path and config_path.exists() else None)
    db_path = db or _resolve_db_path(cfg)
    if not db_path.exists():
        console.print(f"[yellow]![/yellow] No DB at {db_path}; run `video-agent init-db` first.")
        raise typer.Exit(code=0)
    rows = state.list_projects(db_path, status=status_filter, limit=limit)
    if json_out:
        console.print_json(
            data=[r.__dict__ for r in rows],
        )
        return
    table = Table(title=f"Projects ({len(rows)})")
    table.add_column("project_id")
    table.add_column("status")
    table.add_column("shots")
    table.add_column("duration (s)")
    table.add_column("created_at")
    table.add_column("output")
    for r in rows:
        table.add_row(
            r.project_id,
            r.status,
            str(r.num_shots) if r.num_shots is not None else "-",
            f"{r.actual_duration:.1f}" if r.actual_duration else "-",
            r.created_at,
            r.output_path or "-",
        )
    console.print(table)


def _resolve_project_dir(
    project_id: str, cfg: Config, db_path: Optional[Path]
) -> Path:
    """Locate a project's workspace dir by ID — prefers DB, falls back to
    ``<workspace_root>/<project_id>``."""
    if db_path and db_path.exists():
        row = state.get_project(db_path, project_id)
        if row is not None:
            return Path(row.workspace_dir)
    fallback = cfg.runtime.workspace_root / project_id
    if fallback.exists():
        return fallback
    raise typer.BadParameter(
        f"Project {project_id!r} not found in DB or at {fallback}"
    )


@app.command()
def status(
    project_id: str = typer.Argument(...),
    config_path: Optional[Path] = typer.Option(Path("config.toml"), "--config", "-c"),
    db: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """Print per-stage readiness (derived from the workspace filesystem) as JSON."""
    cfg = load_config(config_path if config_path and config_path.exists() else None)
    db_path = db or _resolve_db_path(cfg)
    project_dir = _resolve_project_dir(project_id, cfg, db_path)

    readiness = state.stage_readiness(project_dir)
    record = state.get_project(db_path, project_id) if db_path.exists() else None
    payload = {
        "project_id": project_id,
        "workspace_dir": str(project_dir),
        "db_status": record.status if record else None,
        "num_shots": record.num_shots if record else None,
        "actual_duration": record.actual_duration if record else None,
        "readiness": readiness,
        "next_stage": state.next_stage(readiness),
    }
    console.print_json(data=payload)


@app.command()
def resume(
    project_id: str = typer.Argument(...),
    output: Optional[Path] = typer.Option(
        None, "--output", "-o", help="Override the final MP4 path."
    ),
    config_path: Optional[Path] = typer.Option(Path("config.toml"), "--config", "-c"),
    db: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """Idempotently re-run only the stages that haven't produced artifacts."""
    cfg = load_config(config_path if config_path and config_path.exists() else None)
    _configure_logging(cfg.runtime.log_level)
    db_path = db or _resolve_db_path(cfg)
    project_dir = _resolve_project_dir(project_id, cfg, db_path)

    console.print(f"[bold cyan]Videoflow[/bold cyan] · resuming {project_id}")
    project = resume_project(project_dir, output_path=output, config=cfg, db_path=db_path)
    console.print(f"[green]✓[/green] Output : {project.output_path}")
    if project.shotlist:
        dur = project.shotlist.actual_duration
        dur_str = f"{dur:.1f}s" if dur is not None else "(unknown)"
        console.print(
            f"[green]✓[/green] Shots  : {len(project.shotlist.shots)} · duration {dur_str}"
        )


@app.command()
def trace(
    project_id: str = typer.Argument(...),
    stage: Optional[str] = typer.Option(None, "--stage", "-s", help="Filter by stage name."),
    tail: Optional[int] = typer.Option(None, "--tail", "-n", help="Only show the last N events."),
    timings: bool = typer.Option(
        False,
        "--timings",
        "-t",
        help="Show per-stage wall times instead of raw events.",
    ),
    summary: bool = typer.Option(
        False,
        "--summary",
        help="Print aggregate JSON (total events, failures, wall time, stage timings).",
    ),
    config_path: Optional[Path] = typer.Option(Path("config.toml"), "--config", "-c"),
    db: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """Print the event log for one project.

    By default shows the raw event stream. ``--timings`` pivots to a
    per-stage table of durations; ``--summary`` dumps a JSON blob that's
    easier for dashboards to consume.
    """
    cfg = load_config(config_path if config_path and config_path.exists() else None)
    db_path = db or _resolve_db_path(cfg)
    if not db_path.exists():
        console.print(f"[yellow]![/yellow] No DB at {db_path}")
        raise typer.Exit(code=0)

    if summary:
        data = state.event_summary(db_path, project_id)
        console.print_json(data=data)
        return

    if timings:
        rows = state.stage_timings(db_path, project_id)
        if not rows:
            console.print("(no events)")
            return
        table = Table(title=f"Stage timings · {project_id}")
        table.add_column("stage")
        table.add_column("status")
        table.add_column("started_at")
        table.add_column("duration_s", justify="right")
        for r in rows:
            dur = f"{r.duration_s:.2f}" if r.duration_s is not None else "-"
            started = r.started_at or "-"
            table.add_row(r.stage, r.status, started, dur)
        console.print(table)
        return

    events = state.list_events(db_path, project_id, stage=stage, tail=tail)
    if not events:
        console.print("(no events)")
        return
    table = Table(title=f"Events · {project_id}")
    table.add_column("#")
    table.add_column("ts")
    table.add_column("stage")
    table.add_column("status")
    table.add_column("payload")
    for e in events:
        payload = json.dumps(e.payload, ensure_ascii=False) if e.payload else ""
        table.add_row(str(e.id), e.ts, e.stage, e.status, payload[:60])
    console.print(table)


@app.command()
def doctor(
    config_path: Optional[Path] = typer.Option(Path("config.toml"), "--config", "-c"),
    db: Optional[Path] = typer.Option(None, "--db"),
) -> None:
    """Diagnose FFmpeg, CJK fonts, DB, and MCP dependencies. Exits non-zero on failure."""
    cfg = load_config(config_path if config_path and config_path.exists() else None)
    db_path = db or _resolve_db_path(cfg)

    checks: list[tuple[str, bool, str]] = []

    # 1. Python version.
    ok = sys.version_info >= (3, 11)
    checks.append(("Python ≥ 3.11", ok, sys.version.split()[0]))

    # 2. FFmpeg on PATH.
    ffmpeg = shutil.which("ffmpeg")
    checks.append(("ffmpeg on PATH", ffmpeg is not None, ffmpeg or "not found"))

    # 3. libass support (subtitle burn-in).
    from videoflow.ffmpeg_wrapper import has_filter

    has_subs = has_filter("subtitles") if ffmpeg else False
    checks.append(
        (
            "ffmpeg supports 'subtitles' filter",
            has_subs,
            "yes" if has_subs else "no — subtitles skipped; .ass shipped alongside MP4",
        )
    )

    # 4. CJK font discovered by the renderer.
    from videoflow.renderer import _find_font_file

    try:
        font_path = _find_font_file()
    except Exception:
        font_path = None
    checks.append(
        ("CJK font detected", font_path is not None, str(font_path) if font_path else "fallback (tofu risk)")
    )

    # 5. Workspace writable.
    ws = cfg.runtime.workspace_root
    try:
        ws.mkdir(parents=True, exist_ok=True)
        probe = ws / ".doctor_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append(("workspace writable", True, str(ws)))
    except OSError as exc:
        checks.append(("workspace writable", False, f"{ws}: {exc}"))

    # 6. State DB reachable.
    try:
        state.init_db(db_path)
        with state.connect(db_path) as conn:
            tables = {
                row[0] for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        required = {"projects", "events", "reviews"}
        missing = required - tables
        if missing:
            checks.append(("state DB schema", False, f"missing tables: {missing}"))
        else:
            checks.append(("state DB schema", True, str(db_path)))
    except Exception as exc:  # noqa: BLE001
        checks.append(("state DB schema", False, f"{db_path}: {exc}"))

    # 7. MCP: videoflow-align (word-level subtitle alignment via faster-whisper).
    try:
        from videoflow.mcp_align_client import AlignMCPClient

        client = AlignMCPClient()
        align_available = client.is_available()
        if align_available:
            checks.append(
                (
                    "MCP: videoflow-align",
                    True,
                    f"available (model={cfg.align.model_size}, transport={cfg.align.mcp_transport})",
                )
            )
        else:
            checks.append(
                (
                    "MCP: videoflow-align",
                    False,
                    "not installed — install with: pip install -e ./mcp_servers/align",
                )
            )
    except ImportError:
        checks.append(
            (
                "MCP: videoflow-align",
                False,
                "import failed — check installation",
            )
        )

    # 8. MCP: videoflow-playwright (screen capture).
    try:
        import videoflow_playwright

        checks.append(
            (
                "MCP: videoflow-playwright",
                True,
                f"available (v{videoflow_playwright.__version__})",
            )
        )
    except ImportError:
        checks.append(
            (
                "MCP: videoflow-playwright",
                False,
                "not installed — install with: pip install -e ./mcp_servers/playwright",
            )
        )

    # 9. MCP: videoflow-remotion (animated visuals via Node.js).
    remotion_dir = Path(__file__).parent.parent.parent / "mcp_servers" / "remotion"
    remotion_package = remotion_dir / "package.json"
    remotion_dist = remotion_dir / "dist"
    if remotion_dir.exists() and remotion_package.exists():
        if remotion_dist.exists():
            checks.append(
                (
                    "MCP: videoflow-remotion",
                    True,
                    "available (run: cd mcp_servers/remotion && npm start)",
                )
            )
        else:
            checks.append(
                (
                    "MCP: videoflow-remotion",
                    False,
                    "installed but not built — run: cd mcp_servers/remotion && npm install && npm run bundle",
                )
            )
    else:
        checks.append(
            (
                "MCP: videoflow-remotion",
                False,
                "not installed — see mcp_servers/remotion/README.md",
            )
        )

    table = Table(title="video-agent doctor")
    table.add_column("check")
    table.add_column("ok")
    table.add_column("detail")
    overall_ok = True
    # Soft checks — failure is degraded capability, not a blocker.
    soft_keys = {
        "ffmpeg supports 'subtitles' filter",  # libass missing → .ass shipped alongside
        "MCP: videoflow-align",
        "MCP: videoflow-playwright",
        "MCP: videoflow-remotion",
    }
    for name, ok, detail in checks:
        if ok:
            mark = "[green]✓[/green]"
        elif name in soft_keys:
            mark = "[yellow]·[/yellow]"
        else:
            mark = "[red]✗[/red]"
            overall_ok = False
        table.add_row(name, mark, detail)
    console.print(table)
    if not overall_ok:
        raise typer.Exit(code=1)


@app.command("ui")
def ui_cmd(
    port: int = typer.Option(8501, "--port", "-p", help="Streamlit port."),
    host: str = typer.Option("localhost", "--host", help="Streamlit host."),
    config_path: Optional[Path] = typer.Option(Path("config.toml"), "--config", "-c"),
) -> None:
    """Launch the Streamlit review UI (M4).

    Opens a browser-based interface for reviewing and editing projects.
    Requires `streamlit` to be installed.
    """
    try:
        import streamlit.web.cli as stcli
    except ImportError:
        console.print(
            "[red]✗[/red] streamlit not installed. "
            "Install with: pip install streamlit"
        )
        raise typer.Exit(code=1)

    ui_dir = Path(__file__).parent.parent / "ui"
    if not ui_dir.exists():
        console.print(f"[red]✗[/red] UI directory not found: {ui_dir}")
        raise typer.Exit(code=1)

    console.print(f"[bold cyan]Videoflow[/bold cyan] · launching Streamlit UI")
    console.print(f"  URL: http://{host}:{port}")
    console.print(f"  Dir: {ui_dir}")

    # Run streamlit
    import sys

    sys.argv = [
        "streamlit",
        "run",
        str(ui_dir / "app.py"),
        "--server.port",
        str(port),
        "--server.address",
        host,
        "--browser.gatherUsageStats",
        "false",
    ]
    sys.exit(stcli.main())


@app.command("template")
def template_cmd(
    list_templates: bool = typer.Option(
        False, "--list", "-l", help="List all available templates."
    ),
    show_system_prompt: Optional[str] = typer.Option(
        None, "--prompt", "-p", help="Show system prompt for a template."
    ),
) -> None:
    """Manage and inspect video templates (M6).

    Templates define the style and structure for different video types:
    - explainer: 科普解说
    - news_digest: 新闻摘要
    - story: 故事叙述
    - tutorial: 教程指南
    """
    from videoflow.templates import get_template, list_templates as list_all_templates

    if list_templates:
        templates = list_all_templates()
        table = Table(title="Available Templates")
        table.add_column("Name")
        table.add_column("Display Name")
        table.add_column("Description")
        table.add_column("Tone")
        for tmpl in templates:
            table.add_row(
                tmpl.name,
                tmpl.display_name,
                tmpl.description[:40] + "..." if len(tmpl.description) > 40 else tmpl.description,
                tmpl.tone,
            )
        console.print(table)
        return

    if show_system_prompt:
        tmpl = get_template(show_system_prompt)
        if tmpl is None:
            console.print(f"[red]✗[/red] Template not found: {show_system_prompt}")
            raise typer.Exit(code=1)
        console.print(f"[bold cyan]{tmpl.config.display_name}[/bold cyan]")
        console.print(f"[dim]{tmpl.config.description}[/dim]")
        console.print()
        console.print("[bold]System Prompt:[/bold]")
        console.print(tmpl.get_system_prompt())
        return

    # Default: show help
    console.print("[bold]Videoflow Templates[/bold]")
    console.print("Use --list to see available templates")
    console.print("Use --prompt <name> to show system prompt")


@app.command()
def version() -> None:
    from videoflow import __version__

    console.print(f"videoflow {__version__}")


if __name__ == "__main__":  # pragma: no cover
    app()
