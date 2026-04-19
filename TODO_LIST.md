# Videoflow · TODO 任务列表 / Roadmap

> 基于 [`docs/PRD_zh.md`](./docs/PRD_zh.md) v0.1 拆解,按里程碑分组。
> ✅ = 本 Demo 已实现 · 🟡 = 部分实现/占位 · ⬜ = 未实现

---

## M0 · 项目基础设施(当前 Demo)

- [x] ✅ 仓库初始化 + MIT LICENSE
- [x] ✅ `pyproject.toml` + 依赖声明
- [x] ✅ 中英双语 README
- [x] ✅ 目录结构骨架 (`src/videoflow/`, `tests/`, `examples/`, `workspace/`)
- [x] ✅ 默认 `config.toml`
- [x] ✅ `.gitignore`
- [x] ✅ 本任务列表

## M1 · 最小可跑通 Demo(当前 Demo)

- [x] ✅ Pydantic v2 数据模型: `Shot` / `ShotList` / `Project`
- [x] ✅ Markdown → ShotList Parser(规则切分)
- [x] ✅ edge-tts 异步封装 + 并发生成
- [x] ✅ ASS 字幕生成(基于实际 MP3 时长回写 start/end)
- [x] ✅ 纯 FFmpeg 命令行合成(compose_scene → concat → finalize)
- [x] ✅ TOML 配置加载
- [x] ✅ `video-agent` CLI(generate / parse / tts / render)
- [x] ✅ 《股市反常识》样例输入
- [x] ✅ 单元测试(models / parser / subtitles / ffmpeg / config)
- [x] ✅ 端到端集成测试

## M2 · MCP 工具层与插件体系(PRD §6)

- [ ] ⬜ MCP 客户端(`videoflow.mcp_client`)
- [ ] ⬜ `videoflow-parser` MCP Server(替换规则 Parser,接入 LangExtract + LLM)
- [ ] ⬜ `videoflow-tts` MCP Server(Provider: edge / Azure / ElevenLabs)
- [ ] ⬜ `videoflow-mermaid` MCP Server
- [ ] ⬜ `videoflow-remotion` MCP Server(Node.js 侧)
- [ ] ⬜ `videoflow-playwright` MCP Server
- [ ] ⬜ `videoflow-align` MCP Server(Paraformer / whisper)
- [ ] ⬜ `videoflow-pexels` MCP Server
- [ ] ⬜ `videoflow-ffmpeg` MCP Server
- [ ] ⬜ Provider 基类 + 插件注册表(`videoflow.providers`)

## M3 · LangGraph 编排层(PRD §5)

- [ ] ⬜ `VideoflowState` TypedDict 定义
- [ ] ⬜ StateGraph 拓扑(parser → review1 → asset_factory ↕ tts → align → review2 → composer → review3 → output)
- [ ] ⬜ SQLite Checkpointer 集成(`langgraph.checkpoint.sqlite`)
- [ ] ⬜ `interrupt()` 人工审核中断点
- [ ] ⬜ 审核动作路由(approve / modify / redo / regenerate / recompose)
- [ ] ⬜ 断点恢复命令 `video-agent resume <project_id>`
- [ ] ⬜ 失败重试与降级策略
- [ ] ⬜ Trace 日志落盘(JSONL)

## M4 · 审核 UI(PRD §3.2.4 / §7)

- [ ] ⬜ Streamlit 项目列表页
- [ ] ⬜ Shot 编辑表单(旁白 / 画面规格 / 时长)
- [ ] ⬜ 画面预览(静态图 + MP3 播放器)
- [ ] ⬜ 终片预览与逐镜头跳转
- [ ] ⬜ SQLite 轮询双向通信
- [ ] ⬜ `video-agent ui` 命令拉起 UI

## M5 · 渲染器与素材(PRD §3 / §6.3)

- [ ] ⬜ ChartVisual 动态柱状/折线/饼图(Remotion)
- [ ] ⬜ DiagramVisual Mermaid 渲染链
- [ ] ⬜ TitleCardVisual 关键词高亮
- [ ] ⬜ StockFootageVisual Pexels 搜索 + 缓存
- [ ] ⬜ ScreenCaptureVisual Playwright 录屏
- [ ] ⬜ ImageVisual Ken Burns 动效
- [ ] ⬜ 中文字体打包(Noto Sans CJK SC / Inter / JetBrains Mono)

## M6 · 模板系统

- [ ] ⬜ `explainer` 模板(科普反常识)— Few-shot prompts
- [ ] ⬜ `news_digest` 模板(新闻摘要)— Few-shot prompts
- [ ] ⬜ 模板注册机制 + CLI `--template` 选项
- [ ] ⬜ 用户自定义 Prompt 覆盖

## M7 · 性能与可观测性(PRD §2.2 NFR)

- [ ] ⬜ 缓存层(SHA256 键值 · TTS / visuals / stock)
- [ ] ⬜ 并发策略(`asyncio.gather` Shot 级并行)
- [ ] ⬜ LangGraph Trace 100% 覆盖
- [ ] ⬜ 基准测试 CI(60s 视频 ≤ 10min)
- [ ] ⬜ 长跑稳定性测试(30 天无泄漏)

## M8 · 交付与分发

- [ ] ⬜ Dockerfile + docker-compose.yml
- [ ] ⬜ GitHub Actions CI(Linux/macOS/WSL2 矩阵)
- [ ] ⬜ `video-agent doctor` 环境诊断命令
- [ ] ⬜ 英文版 PRD(`docs/PRD_en.md`)
- [ ] ⬜ Claude Code Skill(`skills/videoflow/SKILL.md`)
- [ ] ⬜ REST API (FastAPI 预留)

## M9 · V1.5+ 未来功能(PRD §1.4.2)

- [ ] ⬜ 抖音/YouTube 自动发布
- [ ] ⬜ 卡通主持人 / 数字人(HeyGen / Wan2.2-S2V)
- [ ] ⬜ 生成式视频大模型(LTX / Sora)
- [ ] ⬜ 多用户权限与云端 SaaS 部署
- [ ] ⬜ Skill Distiller(经验自学习)
- [ ] ⬜ Memory Curation(自动记忆整理)

---

**当前进度**: M0 + M1 完成,即文本→MP4 最短路径已全量跑通。后续里程碑按 PRD §10 建议的 8 周节奏推进。
