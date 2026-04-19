# Videoflow

> **Text in · video out · minimal human touch · fully traceable**

[English](./README_en.md) · [中文](./README_zh.md) · [Full PRD](./docs/PRD_zh.md) · [Roadmap](./TODO_LIST.md)

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              Videoflow Pipeline                              │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
        ┌───────────────────────────┼───────────────────────────┐
        │                           │                           │
        ▼                           ▼                           ▼
┌───────────────┐         ┌───────────────┐           ┌───────────────┐
│    Markdown   │         │      LLM      │           │   Templates   │
│    Script     │         │   Provider    │           │   System      │
│  (input.md)   │         │ (DeepSeek/   │           │  (explainer/ │
│               │         │  OpenAI/     │           │   news/etc.) │
└───────────────┘         │  Anthropic)  │           └───────────────┘
        │                  └───────────────┘                   │
        │                           │                           │
        └───────────┬───────────────┘                           │
                    ▼                                           │
           ┌────────────────┐                                    │
           │     Parser     │◄───────────────────────────────────┘
           │  (ShotList)   │
           └───────┬────────┘
                   │
       ┌───────────┼───────────┐
       │           │           │
       ▼           ▼           ▼
┌──────────┐ ┌──────────┐ ┌──────────┐
│    TTS   │ │ Subtitle │ │ Renderer  │
│ (edge-   │ │  (ASS)   │ │ (Pillow/ │
│  tts)    │ │          │ │ KenBurns)│
└─────┬────┘ └────┬─────┘ └────┬────┘
      │           │           │
      └───────────┴───────────┘
                  │
                  ▼
         ┌────────────────┐
         │     FFmpeg     │
         │  (composer)    │
         └───────┬────────┘
                 │
                 ▼
         ┌────────────────┐
         │   Final MP4    │
         │ (1080×1920)   │
         └────────────────┘
```

### Core Components

| Component | Description | Key Files |
|-----------|-------------|-----------|
| **CLI** | `video-agent` command | `src/videoflow/cli.py` |
| **Parser** | Markdown → ShotList | `src/videoflow/parser.py` |
| **LLM Providers** | DeepSeek/OpenAI/Anthropic | `src/videoflow/providers/` |
| **TTS** | Edge TTS synthesis | `src/videoflow/tts.py` |
| **Renderer** | Pillow + Ken Burns | `src/videoflow/renderer.py` |
| **Subtitles** | ASS generation | `src/videoflow/subtitles.py` |
| **Pipeline** | Orchestration | `src/videoflow/pipeline.py` |
| **State** | SQLite tracking | `src/videoflow/state.py` |

### MCP Servers (Optional)

| Server | Purpose | Location |
|--------|---------|----------|
| `videoflow-align` | Word-level subtitle alignment (faster-whisper) | `mcp_servers/align/` |
| `videoflow-playwright` | Screen capture to MP4 | `mcp_servers/playwright/` |
| `videoflow-remotion` | Animated visuals (6 types) | `mcp_servers/remotion/` |

---

## 🚀 Quick Start

### Prerequisites

- **Python** 3.11+
- **FFmpeg** 6.0+
- **Network** (for TTS and LLM)

```bash
# Verify prerequisites
python --version   # ≥ 3.11
ffmpeg -version   # ≥ 6.0
```

### Installation

```bash
# 1. Clone the repository
git clone <repo-url> video-flow && cd video-flow

# 2. Create virtual environment
python -m venv .venv && source .venv/bin/activate

# 3. Install dependencies
pip install -e ".[dev]"

# 4. Copy environment template (optional - already has demo keys)
cp .env.example .env
```

### First Video (5 minutes)

```bash
# Run the demo pipeline end-to-end
video-agent generate examples/stock-myths/input.md --output workspace/demo.mp4

# Open the result
open workspace/demo.mp4
```

---

## 📖 Usage Guide

### End-to-End Pipeline

```bash
# One command to rule them all
video-agent generate <input.md> --output <output.mp4>
```

### Step-by-Step Pipeline

```bash
# Step 1: Parse Markdown → ShotList JSON
video-agent parse examples/stock-myths/input.md --output shots.json

# Step 2: Generate TTS audio
video-agent tts shots.json --output audio/

# Step 3: Render visuals and compose video
video-agent render workspace/proj_xxx/ --output final.mp4
```

### LLM-Powered Parsing (Recommended)

```bash
# Set API key (already in .env)
export DEEPSEEK_API_KEY=sk-your-key

# Parse with DeepSeek (default)
video-agent llm input.md --output shots.json

# Parse with template
video-agent llm input.md --template explainer --output shots.json
```

### Project Management

```bash
# Initialize state database
video-agent init-db

# List projects
video-agent list

# Check project status
video-agent status <project_id>

# Resume interrupted project
video-agent resume <project_id>

# View event log
video-agent trace <project_id> --timings

# System diagnostics
video-agent doctor
```

### Templates

```bash
# List available templates
video-agent template --list

# Show template prompt
video-agent template --prompt explainer
```

---

## ⚙️ Configuration

### Environment Variables (`.env`)

```env
# LLM Providers (DeepSeek recommended)
DEEPSEEK_API_KEY=sk-xxx

# TTS (edge-tts is free, optional Azure/ElevenLabs)
# AZURE_SPEECH_KEY=xxx

# Stock Footage (optional)
# PEXELS_API_KEY=xxx
```

### Config File (`config.toml`)

```toml
[runtime]
workspace_root = "./workspace"
log_level = "INFO"

[llm]
provider = "deepseek"  # deepseek, openai, anthropic, or "none"
deepseek_model = "deepseek-chat"
temperature = 0.7

[tts]
provider = "edge"
voice = "zh-CN-YunxiNeural"

[rendering]
width = 1080
height = 1920
fps = 30

[align]
provider = "none"  # or "mcp" for word-level subtitles
```

---

## 🧪 Testing

```bash
# Run all tests
pytest tests/ -v

# Run with coverage
pytest tests/ --cov=src/videoflow

# Integration tests (requires FFmpeg + network)
pytest tests/ -v --run-integration
```

---

## 📁 Project Structure

```
video-flow/
├── src/videoflow/
│   ├── cli.py              # video-agent CLI
│   ├── config.py           # TOML config loader
│   ├── models.py           # Pydantic models (Shot, ShotList)
│   ├── parser.py           # Markdown → ShotList
│   ├── pipeline.py         # Pipeline orchestration
│   ├── state.py            # SQLite state management
│   ├── tts.py              # Edge TTS wrapper
│   ├── subtitles.py        # ASS subtitle generator
│   ├── renderer.py         # Pillow + Ken Burns
│   ├── templates.py        # Template registry
│   ├── mermaid.py          # Mermaid CLI wrapper
│   └── providers/          # LLM/TTS providers
│       ├── __init__.py     # Provider registry
│       └── llm_parser.py   # LLM parsing
├── mcp_servers/
│   ├── align/              # Word-level subtitle alignment
│   ├── playwright/         # Screen capture
│   └── remotion/           # Animated visuals (6 types)
├── ui/                     # Streamlit review UI
├── tests/                  # Unit + integration tests
├── examples/stock-myths/   # Demo input
├── docs/                   # PRD documentation
├── config.toml             # Default config
└── .env.example            # Environment template
```

---

## 📋 Feature Matrix

| Feature | Status | Notes |
|---------|--------|-------|
| Rule-based Parser | ✅ | Works offline |
| LLM Parser (DeepSeek) | ✅ | Best for Chinese |
| LLM Parser (OpenAI) | ✅ | GPT-4o |
| LLM Parser (Anthropic) | ✅ | Claude |
| TTS (edge-tts) | ✅ | Free, high quality |
| Ken Burns Effect | ✅ | Image pan/zoom |
| Mermaid Diagrams | ✅ | SVG rendering |
| Streamlit UI | ✅ | Review interface |
| Template System | ✅ | 4 built-in |
| Subtitle Alignment | ✅ | Via MCP |
| Screen Capture | ⚠️ | Via MCP |
| Animated Visuals | ⚠️ | Via MCP (6 types) |
| SQLite State | ✅ | Full tracking |

---

## 🆘 Troubleshooting

### "No module named 'videoflow'"

```bash
source .venv/bin/activate
pip install -e .
```

### "CJK font not found"

The renderer requires Chinese fonts. Install with:

```bash
# macOS
brew install font-noto-sans-cjk

# Ubuntu
sudo apt install fonts-noto-cjk
```

### FFmpeg without libass

Subtitles won't be burned in, but ASS files are still generated:

```bash
# Install FFmpeg with libass
brew install ffmpeg --with-libass  # macOS
```

### LLM parsing fails

```bash
# Verify API key is set
echo $DEEPSEEK_API_KEY

# Or use rule-based parser (offline)
video-agent parse input.md
```

---

## 📚 Documentation

| Document | Language | Description |
|---------|----------|-------------|
| [README.md](./README.md) | EN+ZH | This file, quick navigation |
| [README_en.md](./README_en.md) | English | Full English documentation |
| [README_zh.md](./README_zh.md) | 中文 | Complete Chinese documentation |
| [PRD_zh.md](./docs/PRD_zh.md) | 中文 | Product Requirements Document |
| [TODO_LIST.md](./TODO_LIST.md) | EN | Development roadmap |

---

## 🤝 Contributing

See [`TODO_LIST.md`](./TODO_LIST.md) for the development roadmap. Areas for contribution:

- Mermaid/Remotion/Playwright integration
- Additional TTS/LLM providers
- More video templates
- UI/UX improvements

---

## 📄 License

[MIT](./LICENSE)
