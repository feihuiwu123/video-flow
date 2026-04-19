# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project scope

This repo is the **"smallest runnable demo"** of Videoflow — a text-to-video pipeline. The design target is the full V1.0 MVP in `docs/PRD_zh.md` (5117 lines, Chinese), but the current code only covers the shortest happy path:

```
Markdown script → Shot JSON → edge-tts narration → ASS subtitles → FFmpeg → 1080×1920 MP4
```

Milestones beyond this demo (MCP servers, LangGraph state machine, Streamlit review UI, Mermaid/Remotion/Playwright renderers) are tracked in `TODO_LIST.md` as M2-M9. When adding features, check `TODO_LIST.md` first — it's the authoritative gap list.

## Commands

```bash
# Env setup (Python 3.11+, FFmpeg 6+ required on PATH)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Run the pipeline end-to-end
video-agent generate examples/stock-myths/input.md --output workspace/demo.mp4

# Subcommands for stage-by-stage work
video-agent parse  <input.md>                     # Markdown → Shot JSON
video-agent tts    <project>/shots.json --output <project>/audio
video-agent render <project_dir> --output out.mp4

# Unit tests (offline, network mocked)
pytest tests/ -v

# Single test
pytest tests/test_parser.py::TestParseMarkdown::test_produces_valid_shotlist -v

# Integration test (hits edge-tts + FFmpeg — requires network)
pytest tests/ -v --run-integration
```

There is no linter or formatter configured — do not introduce one without discussing with the user.

## Architecture

The pipeline is a linear stage graph glued together in `src/videoflow/pipeline.py`. Every stage has a stable seam so the next milestones (MCP servers, LangGraph nodes) can slot in without refactoring callers:

```
parser.parse_file()            →  ShotList (draft, estimated timings)
tts.synthesize_all() + retime  →  ShotList (real timings from MP3 durations)
renderer.render_title_card     →  per-shot PNG frame (Pillow, CJK font)
subtitles.write_ass()          →  ASS file (sidecar)
ffmpeg_wrapper.compose_scene   →  per-shot MP4s (PNG looped + MP3)
ffmpeg_wrapper.concat_scenes   →  concatenated MP4 (copy codec)
pipeline.finalize()            →  subtitle burn-in (or skip, see below)
```

### Key invariants

- **"Sound first, picture after"** (PRD §5): TTS generates audio, `ShotList.retime_from_audio()` overwrites `shot.start/end` with real durations. The first parsed timings are only estimates — never rely on them after the TTS stage.
- **Provider abstraction is load-bearing**: `TTSProvider` in `tts.py` is an ABC. The rule-based `parser.py` is a temporary implementation — its signature mirrors a future LLM/LangExtract parser. Don't couple callers to concrete classes.
- **Shot IDs are `S\d{2,3}`** (Pydantic regex-validated). Cross-stage file naming (`audio/S01.mp3`, `scenes/S01.mp4`) depends on this format.
- **`VisualSpec` is multi-type by design**. Only `TitleCardVisual` ships today. The PRD §4 lists `ChartVisual`, `DiagramVisual`, `StockFootageVisual`, `ScreenCaptureVisual`, `ImageVisual` — use Pydantic discriminated unions (`Field(discriminator="type")`) when adding them.

### FFmpeg gotchas

- Paths inside `-vf` filter arguments must be escaped via `ffmpeg_wrapper.escape_filter_path()` — `:` is a filter option separator, and subprocess list args don't let the shell strip quotes.
- `has_filter("subtitles")` detects whether the local ffmpeg was built with libass. Stock Homebrew FFmpeg on macOS is **not**, so `pipeline.finalize()` falls back to shipping the `.ass` file alongside the MP4 instead of failing. Don't regress this — integration tests rely on it.
- Because `drawtext` / `subtitles` / `ass` may all be missing, on-screen text comes from **pre-rasterised PNGs via Pillow** (see `renderer.py`), not from FFmpeg filters. Pillow needs a CJK font — `_FONT_CANDIDATES` probes macOS/Linux/Windows paths; falls back to Pillow default (tofu for Chinese) if none found.
- Scene MP4s use identical codec/resolution/fps so `concat_scenes` can use `-c copy` (instantaneous). Any new renderer must preserve this or the concat path needs reworking.

### Workspace layout per run

Every `video-agent generate` creates `workspace/proj_<YYMMDDhhmmss>/` with:

```
shots_draft.json   # pre-TTS shotlist (estimated timings)
shots.json         # post-TTS shotlist (real timings, audio paths filled)
audio/S01.mp3 …    # one per shot
scenes/S01.mp4 …   # per-shot rendered clips
subtitles/final.ass
project.json       # summary metadata
```

The CLI `render` subcommand assumes this layout and is how you resume after manual edits.

### Test conventions

- Unit tests mock all subprocess calls — they assert on argv shape via `unittest.mock.patch("videoflow.ffmpeg_wrapper._run", …)`. Real FFmpeg/edge-tts is only invoked by `tests/test_integration.py`.
- The `integration` pytest marker is registered in `pyproject.toml` and gated by `--run-integration` (see `tests/conftest.py`). Do not run integration tests in CI without explicit opt-in.

## When extending

- **Before adding a new visual type**: read PRD §4 for the required fields (`type` discriminator, data shape), then update `models.py`, `parser.py` (how it's produced), and add a renderer — don't half-wire it.
- **Before replacing the rule-based parser**: keep `parse_file()` as a fallback. The PRD calls for LangExtract + LLM planning; the seam is the `ShotList` return type.
- **Config changes are forward-compatible**: `config.py` silently ignores unknown TOML keys. Prefer adding optional fields with defaults over breaking existing `config.toml` files.
