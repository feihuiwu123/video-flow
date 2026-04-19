# Videoflow

> **文本输入 · 视频输出 · 人工最少 · 全程可追溯**

Videoflow 是一款面向"**数据驱动、文本先行、图表精准**"短视频场景的开源工程化流水线,把 Markdown 文案一步到位转成可发布的竖屏 MP4。

[English README](./README_en.md) · [完整 PRD](./docs/PRD_zh.md) · [TODO 任务列表](./TODO_LIST.md)

---

## ✨ 项目状态

当前仓库是 PRD 中 **V1.0 MVP 的"最小可跑通 Demo"**,已经打通:

```
Markdown 文案  ──▶  分镜 (Shot JSON)  ──▶  edge-tts 旁白  ──▶  ASS 字幕  ──▶  FFmpeg 合成  ──▶  1080×1920 MP4
```

完整 MVP(8 个 MCP Server、LangGraph 状态机、Streamlit 审核 UI、Mermaid/Remotion/Playwright 渲染器等)的路线图见 [`TODO_LIST.md`](./TODO_LIST.md)。

## 🎯 核心价值

| 维度 | 本 Demo 表现 | 完整 MVP 目标 |
|------|-------------|--------------|
| **自动化** | 单条命令一步产出 MP4 | Light 模式 1 次人工确认 |
| **工业化** | 纯 FFmpeg 字符串拼接,可重入 | 全链路 LangGraph 状态机 + SQLite 检查点 |
| **可扩展** | Provider 抽象基类就绪 | MCP 插件 < 100 行新增 Provider |
| **精准** | 静态背景色 + 中文 ASS 字幕 | Mermaid + Remotion 程序化图表 |
| **开源友好** | MIT + 双语文档 | clone → 5 分钟出视频 |

## 🛠️ 环境要求

- **Python** 3.11+
- **FFmpeg** 6.0+ (macOS `brew install ffmpeg` / Ubuntu `apt install ffmpeg`)
- **网络**(edge-tts 需要访问微软接口;离线场景可替换为本地 TTS Provider)

验证:

```bash
python --version      # ≥ 3.11
ffmpeg -version       # ≥ 6.0
```

## 🚀 5 分钟快速上手

```bash
# 1. 克隆
git clone <repo-url> video-flow && cd video-flow

# 2. 安装(推荐使用 uv 或 venv)
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# 3. 跑样例(《股市反常识》)
video-agent generate examples/stock-myths/input.md --output workspace/demo.mp4

# 4. 查看产物
open workspace/demo.mp4
```

命令行选项:

```bash
video-agent generate <input.md> \
    --output workspace/out.mp4 \
    --voice zh-CN-YunxiNeural \
    --config ./config.toml
```

还可以单独跑每一步:

```bash
video-agent parse  examples/stock-myths/input.md   # 输出 Shot JSON
video-agent tts    workspace/proj_xxx/shots.json   # 为每个分镜生成 MP3
video-agent render workspace/proj_xxx              # FFmpeg 合成
```

## 🗂️ 项目结构

```
video-flow/
├── src/videoflow/
│   ├── __init__.py
│   ├── cli.py              # video-agent 命令入口
│   ├── config.py           # TOML 配置加载
│   ├── models.py           # Shot / ShotList / Project (Pydantic v2)
│   ├── parser.py           # Markdown → Shot JSON (规则 + 可插拔 LLM)
│   ├── tts.py              # edge-tts 异步封装
│   ├── subtitles.py        # ASS 字幕生成
│   ├── ffmpeg_wrapper.py   # 纯命令行 FFmpeg 合成
│   └── pipeline.py         # 串联 Parser→TTS→Subtitle→FFmpeg
├── tests/                  # pytest 单元测试
├── examples/stock-myths/   # 《股市反常识》样例
├── docs/PRD_zh.md          # 完整产品需求文档
├── config.toml             # 默认配置
├── LICENSE                 # MIT
├── README_zh.md            # 本文件
├── README_en.md            # 英文版
└── TODO_LIST.md            # 基于 PRD 的完整路线图
```

## 🧪 运行测试

```bash
# 单元测试(离线,mock 掉网络调用)
pytest tests/ -v

# 集成测试(端到端,需要 FFmpeg 和网络)
pytest tests/test_integration.py -v --run-integration
```

## 🧩 工作原理

```
examples/stock-myths/input.md
        │
        ▼
   parser.py  ── 按段落+空行切分,生成 shots.json
        │
        ▼
   tts.py     ── 并发调用 edge-tts,每条旁白生成 <shot_id>.mp3
        │
        ▼
   subtitles.py ── 根据实际 MP3 时长,输出 ASS 文件(回写 shot.start/end)
        │
        ▼
   ffmpeg_wrapper.py ── compose_scene → concat → finalize,产出 1080x1920 MP4
```

输出目录结构:

```
workspace/proj_<timestamp>/
├── shots.json          # 确认后的分镜稿
├── audio/
│   ├── S01.mp3
│   └── ...
├── subtitles/
│   └── final.ass
├── scenes/             # 单镜头 MP4
└── final.mp4           # 最终产物
```

## 🤝 贡献

本 Demo 仅实现最短链路,欢迎贡献以下方向(见 [`TODO_LIST.md`](./TODO_LIST.md) M2-M4 阶段):

- Mermaid / Remotion / Playwright 渲染器
- LangGraph 状态机与 SQLite 检查点
- Streamlit 审核 UI
- 更多 TTS / LLM / 字幕对齐 Provider
- 更多模板(news_digest, tutorial…)

## 📄 许可证

[MIT](./LICENSE)

## 🙏 致谢

- [LangGraph](https://github.com/langchain-ai/langgraph) · 状态机编排
- [edge-tts](https://github.com/rany2/edge-tts) · 免费微软 TTS
- [FFmpeg](https://ffmpeg.org/) · 视频合成引擎
- [MCP](https://modelcontextprotocol.io/) · 工具协议
