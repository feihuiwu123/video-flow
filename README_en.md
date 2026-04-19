# Videoflow

> Text in · Video out · AI-powered short video pipeline

[中文](./README_zh.md) · [Full PRD](./docs/PRD_zh.md) · [Roadmap](./TODO_LIST.md)

---

## 5-Minute Quickstart

```bash
# 1. Create virtual environment
python -m venv .venv && source .venv/bin/activate

# 2. Install dependencies
pip install -e ".[dev]"

# 3. Generate video with AI shot planning
python -m videoflow.cli generate examples/stock-myths/input.md --plan --output workspace/demo.mp4

# 4. Open result
open workspace/demo.mp4
```

---

## Core Commands

```bash
# Plan: Generate professional shot plan using LLM
python -m videoflow.cli plan "your topic or content" -o plan.json

# Generate: Create video from Markdown or plan file
python -m videoflow.cli generate input.md --output out.mp4           # From Markdown
python -m videoflow.cli generate input.md --plan --output out.mp4   # With AI planning
python -m videoflow.cli generate plan.json --output out.mp4          # From plan file

# Parse: Convert Markdown to shot structure
python -m videoflow.cli parse input.md --output shots.json

# Other commands
python -m videoflow.cli list                          # List projects
python -m videoflow.cli doctor                        # System diagnostics
```

---

## Features

| Feature | Status | Description |
|---------|--------|-------------|
| AI Shot Planning | ✅ | LLM generates professional shot-by-shot scripts |
| Chart Rendering | ✅ | Bar, pie, line, scatter charts |
| Diagram Rendering | ✅ | Mermaid DSL flowcharts |
| Image Rendering | ✅ | Local/URL images |
| Text-to-Speech | ✅ | Free edge-tts, multiple voices |
| Interactive Mode | ✅ | Select visuals, voices before generation |
| Subtitles | ✅ | ASS format |
| Video Composition | ✅ | FFmpeg concatenation |

---

## AI Shot Planning

Generate professional video scripts with AI:

```bash
# Plan with topic text
python -m videoflow.cli plan "公司为什么上市分钱给陌生人？" --duration 60

# Plan from Markdown file
python -m videoflow.cli plan examples/stock-myths/input.md

# Save plan to file
python -m videoflow.cli plan "your topic" -o myplan.json

# Generate video from plan
python -m videoflow.cli generate myplan.json --output out.mp4
```

After generating the plan, you'll be prompted:
- **Y**: Continue to video generation
- **n**: Cancel and save plan

Use `--no-interactive` to skip the confirmation prompt.

Output example:
```
✓ Plan: 公司上市，为何分钱给陌生人？
Style: 快节奏，信息密度高、反认知
Duration: ~60s (8 shots)

┏━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━┓
┃ Shot ┃ Duration ┃ Visual       ┃ Preview            ┃
┡━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━┩
│ S01  │       5s │ title_card  │ [悬念标题] 口播... │
│ S02  │       8s │ chart (bar) │ [数据对比] 口播... │
│ S03  │      10s │ diagram     │ [流程图] 口播...   │
└──────┴──────────┴──────────────┴────────────────────┘
```

### Visual Types in Shots

| Type | Description | Best For |
|------|-------------|----------|
| `title_card` | Title slide | Opening hooks, summaries |
| `chart` | Bar/Line/Pie | Data comparison, trends |
| `diagram` | Mermaid flowchart | Process, relationships |
| `image` | Image with caption | Real photos |

---

## Interactive Mode

By default, the CLI shows a preview and lets you customize:

```bash
python -m videoflow.cli generate input.md --plan --output out.mp4
```

```
                           Shot Plan (8 shots)
┏━━━━━┳━━━━━━━━━━━━┳━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━┓
┃ ID  ┃ Type       ┃ Duration ┃ Visual/Title        ┃
┡━━━━━╇━━━━━━━━━━━━╇━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━┩
│ S01 │ title_card │     6.0s │ 公司明明赚钱...      │
│ S02 │ chart     │    10.0s │ [bar] IPO融资对比   │
└─────┴────────────┴──────────┴──────────────────────┘

Customize Visuals:
Edit visual types for each shot? (y/N): y
Select visual for S02:
  1. 📝 标题卡片
  2. 📊 图表 (Bar/Line/Pie)
  3. 🔄 流程图 (Mermaid)
Enter number (default: current): 2  → 切换为图表

TTS Voice:
  Current: zh-CN-YunxiNeural
Change voice? (y/N): y
  1. 🌟 云希 (男声, 活泼阳光)
  2. 💫 晓晓 (女声, 温暖自然)
  3. 📺 云扬 (男声, 专业播音)
  ...

Proceed with video generation? [y]:
```

### Available TTS Voices

| Voice | Description |
|-------|-------------|
| `zh-CN-YunxiNeural` | 🌟 Male, lively sunshine (default) |
| `zh-CN-XiaoxiaoNeural` | 💫 Female, warm natural |
| `zh-CN-YunyangNeural` | 📺 Male, professional news |
| `zh-CN-YunjianNeural` | ⚽ Male, passionate sports |
| `zh-CN-XiaoyiNeural` | 🎬 Female, cartoon lively |
| `en-US-AriaNeural` | 🇺🇸 English female |

### Skip Interactive Mode

```bash
# Non-interactive (for scripts/CI)
python -m videoflow.cli generate input.md --plan --no-interactive --output out.mp4
```

---

## Input Format

### Markdown with Visual Blocks

```markdown
# Video Title

## Section 1

Content here...

:::chart bar
title: Data Comparison
data:
  labels: [A, B, C]
  values: [100, 200, 150]
color: default
:::

```mermaid
graph LR
    A --> B --> C
```
```

### Supported Visual Blocks

| Block | Syntax |
|-------|--------|
| Bar Chart | `:::chart bar` with `data:` |
| Line Chart | `:::chart line` |
| Pie Chart | `:::chart pie` |
| Flowchart | ` ```mermaid` code block |
| Image | `:::image path: ...` |

---

## Configuration

### Environment Variables

Set API keys in `.env`:

```bash
DEEPSEEK_API_KEY=sk-xxx      # LLM planning (recommended)
OPENAI_API_KEY=sk-xxx        # Alternative LLM
```

### Config File

Edit `config.toml`:

```toml
[tts]
provider = "edge"
voice = "zh-CN-YunxiNeural"

[rendering]
width = 1080
height = 1920
fps = 30
```

---

## Troubleshooting

**"No module named 'videoflow'"**
```bash
source .venv/bin/activate
pip install -e .
```

**Missing CJK fonts**
```bash
# macOS
brew install font-noto-sans-cjk
# Ubuntu
sudo apt install fonts-noto-cjk
```

**Subtitles not burned in**
Homebrew FFmpeg doesn't include libass. ASS files are still generated alongside MP4.

---

## Related Documents

- [中文文档](./README_zh.md)
- [Product Requirements](./docs/PRD_zh.md)
- [Development Roadmap](./TODO_LIST.md)

---

## License

[MIT](./LICENSE)
