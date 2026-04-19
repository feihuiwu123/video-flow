# Videoflow

> **Text in · video out · minimal human touch · fully traceable**

Videoflow is an open-source, engineered pipeline for **data-driven, text-first, chart-accurate** short-form videos. Feed it a Markdown script and get a publishable 1080×1920 MP4 back.

[中文 README](./README_zh.md) · [Full PRD (Chinese)](./docs/PRD_zh.md) · [TODO Roadmap](./TODO_LIST.md)

---

## ✨ Project Status

This repo is the **"smallest runnable demo"** of the V1.0 MVP described in the PRD. The end-to-end path is live:

```
Markdown script  ──▶  Shot JSON  ──▶  edge-tts narration  ──▶  ASS subtitles  ──▶  FFmpeg compose  ──▶  1080×1920 MP4
```

The roadmap to the full MVP (8 MCP servers, LangGraph state machine, Streamlit review UI, Mermaid/Remotion/Playwright renderers) lives in [`TODO_LIST.md`](./TODO_LIST.md).

## 🎯 Value Proposition

| Dimension | This Demo | Full MVP Target |
|-----------|-----------|-----------------|
| **Automation** | One CLI command → MP4 | Light mode: 1 human confirmation |
| **Industrial** | Pure FFmpeg CLI, re-entrant | LangGraph + SQLite checkpoints |
| **Extensible** | Provider abstract base ready | MCP plugin < 100 LoC per Provider |
| **Precision** | Solid background + Chinese ASS subtitles | Programmatic charts via Mermaid + Remotion |
| **OSS friendly** | MIT + bilingual docs | clone → 5 min → first video |

## 🛠️ Requirements

- **Python** 3.11+
- **FFmpeg** 6.0+ (`brew install ffmpeg` on macOS, `apt install ffmpeg` on Ubuntu)
- **Network** — edge-tts hits Microsoft endpoints; swap in a local TTS provider for offline use.

Verify:

```bash
python --version      # ≥ 3.11
ffmpeg -version       # ≥ 6.0
```

## 🚀 5-Minute Quickstart

```bash
# 1. Clone
git clone <repo-url> video-flow && cd video-flow

# 2. Install (uv or venv)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. Run the sample ("Stock Market Counterintuitive Facts")
video-agent generate examples/stock-myths/input.md --output workspace/demo.mp4

# 4. Open the result
open workspace/demo.mp4
```

CLI options:

```bash
video-agent generate <input.md> \
    --output workspace/out.mp4 \
    --voice zh-CN-YunxiNeural \
    --config ./config.toml
```

Run the pipeline step by step:

```bash
video-agent parse  examples/stock-myths/input.md   # Emit Shot JSON
video-agent tts    workspace/proj_xxx/shots.json   # Generate an MP3 per shot
video-agent render workspace/proj_xxx              # FFmpeg composition
```

## 🗂️ Layout

```
video-flow/
├── src/videoflow/
│   ├── __init__.py
│   ├── cli.py              # `video-agent` command
│   ├── config.py           # TOML loader
│   ├── models.py           # Shot / ShotList / Project (Pydantic v2)
│   ├── parser.py           # Markdown → Shot JSON (rule-based; LLM-pluggable)
│   ├── tts.py              # edge-tts async wrapper
│   ├── subtitles.py        # ASS subtitle generator
│   ├── ffmpeg_wrapper.py   # Pure-CLI FFmpeg composer
│   └── pipeline.py         # Parser → TTS → Subtitles → FFmpeg
├── tests/                  # pytest suites
├── examples/stock-myths/   # Sample script
├── docs/PRD_zh.md          # Full PRD (Chinese)
├── config.toml             # Default config
├── LICENSE                 # MIT
├── README_zh.md            # Chinese README
├── README_en.md            # This file
└── TODO_LIST.md            # Full roadmap derived from the PRD
```

## 🧪 Tests

```bash
# Unit tests — offline, network calls mocked
pytest tests/ -v

# Integration — end-to-end, needs FFmpeg + network
pytest tests/test_integration.py -v --run-integration
```

## 🧩 How It Works

```
examples/stock-myths/input.md
        │
        ▼
   parser.py       → split by headings + paragraphs → shots.json
        │
        ▼
   tts.py          → concurrent edge-tts → <shot_id>.mp3
        │
        ▼
   subtitles.py    → real MP3 duration → ASS file (writes back shot.start/end)
        │
        ▼
   ffmpeg_wrapper  → compose_scene → concat → finalize → 1080×1920 MP4
```

Output layout:

```
workspace/proj_<timestamp>/
├── shots.json          # Approved shot list
├── audio/
│   ├── S01.mp3
│   └── ...
├── subtitles/
│   └── final.ass
├── scenes/             # Per-shot MP4s
└── final.mp4           # Final deliverable
```

## 🤝 Contributing

The demo covers the shortest happy path. Good first contributions (see [`TODO_LIST.md`](./TODO_LIST.md) milestones M2-M4):

- Mermaid / Remotion / Playwright renderers
- LangGraph state machine with SQLite checkpoints
- Streamlit review UI
- Additional TTS / LLM / subtitle-align providers
- More templates (news_digest, tutorial, …)

## 📄 License

[MIT](./LICENSE)

## 🙏 Acknowledgements

- [LangGraph](https://github.com/langchain-ai/langgraph) — state-machine orchestration
- [edge-tts](https://github.com/rany2/edge-tts) — free Microsoft TTS
- [FFmpeg](https://ffmpeg.org/) — video composition engine
- [MCP](https://modelcontextprotocol.io/) — tool protocol
