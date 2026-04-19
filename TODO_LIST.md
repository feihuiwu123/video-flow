# Videoflow · TODO 任务列表 / Roadmap

> 基于 [`docs/PRD_zh.md`](./docs/PRD_zh.md) v0.1 拆解,按里程碑分组。
> ✅ = 本 Demo 已实现 · 🟡 = 部分实现/占位 · ⬜ = 未实现

## 编排选型规则(M3 起适用)

为了降低编排复杂度、对齐 Claude Code 生态、收敛进程数,在"Skill / CLI / MCP"三者之间按下表取舍:

| 选型 | 适用条件 |
|------|---------|
| **Skill + CLI** | 短生命周期、无状态、纯 Python 能做、由 Claude Code 触发 |
| **CLI 独立子命令** | Skill 之下的"原子操作",可被 Skill 串起来,也能脱离 Claude 独立运行 |
| **MCP Server** | 满足以下任一条件才用:①模型/运行时常驻(冷启 >3s 或占内存 >200MB)· ②跨语言运行时(Node / Browser)· ③需要被非 Claude 客户端复用 |

这意味着原 PRD 的 8 个 MCP 在本项目中**收窄为 3 个**:`videoflow-align` / `videoflow-remotion` / `videoflow-playwright`;其余能力(parser / tts / mermaid / pexels / ffmpeg)都以 CLI 子命令形式存在,由 Skill 编排。

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
- [x] ✅ Pillow 标题卡渲染器(CJK 字体自动探测,无需 libass)
- [x] ✅ 纯 FFmpeg 命令行合成(compose_scene → concat → finalize)
- [x] ✅ TOML 配置加载
- [x] ✅ `video-agent` CLI(generate / parse / tts / render)
- [x] ✅ 《股市反常识》样例输入
- [x] ✅ 单元测试(models / parser / subtitles / ffmpeg / config)
- [x] ✅ 端到端集成测试

## M2 · Provider 抽象(收窄版)

> 原 M2 的 8 个 MCP Server 已拆解:3 个进 M3,其余下沉为 CLI 子命令(见"编排选型规则")。这里只保留 **Provider 插件体系** 给 TTS/LLM 等能力做可替换。

- [x] ✅ Provider 基类 + 注册表(`videoflow.providers`)
- [x] ✅ LLM Provider:DeepSeek / OpenAI / Anthropic 实现 + CLI `video-agent llm`
- [ ] ⬜ TTS Provider:Azure / ElevenLabs 实现(edge 已在 M1 完成)

## M3 · 编排层:Skill-first + 3 个 MCP + SQLite 索引

> **关键设计决策**(见文首"编排选型规则"):
> - **编排核心是 Skill 套件**,不是 LangGraph 状态机
> - **真相源 = 文件系统**,SQLite 仅做**索引 + 事件流 + 审核动作**三张表
> - **只做 3 个 MCP**:Paraformer/whisper 的模型常驻、Remotion 的 Node 运行时、Playwright 的 Chromium 实例
> - 分 5 期滴水提交,每期独立 commit;外部依赖必须真实跑通(不写空壳)

### M3.1 · Skill 套件 + State 模块 + CLI 骨架扩展

- [x] ✅ `.claude/skills/videoflow/SKILL.md` 入口清单 + frontmatter
- [x] ✅ `.claude/skills/videoflow/generate.md` auto 模式端到端
- [x] ✅ `.claude/skills/videoflow/review.md` light 模式审核(读 shots.json → 向用户确认 → 写回)
- [x] ✅ `.claude/skills/videoflow/resume.md` 幂等续跑
- [x] ✅ `src/videoflow/state.py` SQLite 薄封装(3 张表:`projects` / `events` / `reviews`)
- [x] ✅ `video-agent init-db` 子命令(幂等建表)
- [x] ✅ `video-agent list [--status S]` 从 DB 查项目列表
- [x] ✅ `video-agent status <id>` 输出 JSON 阶段就绪状态
- [x] ✅ `video-agent resume <id>` 幂等续跑,跳过已完成阶段
- [x] ✅ `video-agent trace <id>` 从 events 表 tail
- [x] ✅ `video-agent doctor` FFmpeg / CJK 字体 / DB / 依赖 MCP 的诊断
- [x] ✅ state 模块单元测试 + 幂等性测试(21 tests,tests/test_state.py)

### M3.2 · `videoflow-align` MCP Server

- [x] ✅ MCP Python SDK 初始化(`mcp_servers/align/`)
- [x] ✅ 工具:`align_subtitle(audio_path, text, output_ass)` → 带字级时间戳的 ASS
- [x] ✅ 引擎:**faster-whisper base**(~150MB,多语种,CPU 友好)
- [x] ✅ 启动脚本 + README + pyproject
- [x] ✅ MCP 协议集成测试(spawn server → JSON-RPC 调用 → 断言 ASS 产物)
- [x] ✅ `videoflow.subtitles` 改造:可选从 align MCP 拉字级时间戳
- [x] ✅ `video-agent align` CLI 子命令
- [x] ✅ `video-agent doctor` 集成检查 align MCP 可用性
- [x] ✅ 配置项 `[align]` 支持 (provider / model_size / language)
- [x] ✅ `.env.example` 环境变量模板 (M3.3-M4 预留)

### M3.3 · `videoflow-playwright` MCP Server

- [x] ✅ MCP Python SDK 初始化(`mcp_servers/playwright/`)
- [x] ✅ 工具:`capture_url(url, duration, viewport)` → MP4
- [x] ✅ 工具:`capture_url_with_interactions` 支持 click/scroll/type
- [x] ✅ Chromium 热实例复用(避免每次冷启)
- [x] ✅ 工具:`check_browser` 健康检查
- [x] ✅ README + 安装指引(`playwright install chromium`)
- [x] ✅ 单元测试 + 集成测试框架
- [x] ✅ `video-agent doctor` 集成检查 playwright MCP 可用性

### M3.4a · Remotion MCP 脚手架 + TitleCard + ChartVisual

- [x] ✅ Node.js 子项目 `mcp_servers/remotion/`(TypeScript + Remotion 4 + React 18)
- [x] ✅ MCP TS SDK 包装 (`@modelcontextprotocol/sdk`)
- [x] ✅ 中文字体支持 (Noto Sans SC)
- [x] ✅ `TitleCardComposition`(关键词高亮 + 入场动画)
- [x] ✅ `ChartComposition`(bar/line/pie + 动画)
- [x] ✅ 构建脚本(`npm run bundle`)
- [x] ✅ README + 安装指引

### M3.4b · Remotion 剩余 4 类 VisualSpec

> ⚠️ 依赖外部凭证:StockFootage 需 **Pexels API key**(免费,需用户提供);ScreenCapture 依赖 M3.3 Playwright MCP 产出的 MP4。

- [x] ✅ `DiagramComposition`(嵌入 Mermaid 预渲染 SVG,支持 sequential 动画)
- [x] ✅ `StockFootageComposition`(loop + Ken Burns;调 Pexels API 拉素材 + 缓存)
- [x] ✅ `ScreenCaptureComposition`(嵌入 Playwright MP4;支持叠加标注)
- [x] ✅ `ImageComposition`(Ken Burns 动效)
- [x] ✅ `VisualSpec` 全 6 类 → Remotion Composition 路由映射
- [ ] ⬜ 端到端:`auto` 模式全链路跑通,生成一条含 4 种画面类型的混合视频

## M4 · 审核 UI — 可选第二通道(PRD §3.2.4 / §7)

> 注:M3.1 的 Skill 审核已覆盖 Light 模式。Streamlit UI 仅作为**非 Claude Code 用户**的第二通道。SQLite `reviews` 表已在 M3.1 定义,UI 直接读该表。

- [x] ✅ Streamlit 项目列表页(查 M3.1 的 `projects` 表)
- [x] ✅ Shot 编辑表单(旁白 / 画面规格 / 时长)
- [x] ✅ 画面预览(静态图 + MP3 播放器)
- [x] ✅ 终片预览与逐镜头跳转
- [x] ✅ SQLite `reviews` 表写入 + Worker 轮询消费
- [x] ✅ `video-agent ui` 命令拉起 UI

## M5 · 渲染器打磨(M3.4 的延展)

> M3.4a/b 已实现全 6 类 VisualSpec 的 Remotion 渲染。此里程碑负责**质量打磨**:动画细节、字体微调、Mermaid CLI 独立集成。

- [x] ✅ Mermaid CLI 独立封装(当前在 Remotion 内嵌;抽出来可被 Skill 单独调)
- [x] ✅ ChartVisual 动画缓动曲线 + 多数据对比场景
- [x] ✅ TitleCardVisual 入场/出场转场库
- [x] ✅ ImageVisual Ken Burns 方向/速度参数化
- [x] ✅ 字体加权组合(Inter + JetBrains Mono 混排)
- [x] ✅ 性能:Remotion 渲染并发度调优

## M6 · 模板系统

- [x] ✅ `explainer` 模板(科普反常识)— Few-shot prompts
- [x] ✅ `news_digest` 模板(新闻摘要)— Few-shot prompts
- [x] ✅ 模板注册机制 + CLI `--template` 选项
- [x] ✅ 用户自定义 Prompt 覆盖

## M7 · 性能与可观测性(PRD §2.2 NFR)

- [ ] ⬜ 缓存层(SHA256 键值 · TTS / visuals / stock)
- [ ] ⬜ 并发策略(`asyncio.gather` Shot 级并行)
- [ ] ⬜ events 表查询接口 + dashboard(100% trace 覆盖)
- [ ] ⬜ 基准测试 CI(60s 视频 ≤ 10min)
- [ ] ⬜ 长跑稳定性测试(30 天无泄漏)

## M8 · 交付与分发

- [ ] ⬜ Dockerfile + docker-compose.yml(主包 + 3 个 MCP 容器)
- [ ] ⬜ GitHub Actions CI(Linux/macOS/WSL2 矩阵)
- [ ] ⬜ 英文版 PRD(`docs/PRD_en.md`)
- [ ] ⬜ REST API (FastAPI 预留,消费 `projects` 表)

## M9 · V1.5+ 未来功能(PRD §1.4.2)

- [ ] ⬜ 抖音/YouTube 自动发布
- [ ] ⬜ 卡通主持人 / 数字人(HeyGen / Wan2.2-S2V)
- [ ] ⬜ 生成式视频大模型(LTX / Sora)
- [ ] ⬜ 多用户权限与云端 SaaS 部署
- [ ] ⬜ Skill Distiller(经验自学习)
- [ ] ⬜ Memory Curation(自动记忆整理)

---

**当前进度**: M0 + M1 + M2(L部分) + M3.1 + M3.2 + M3.3 + M3.4a + M3.4b + M4 + M5 + M6 完成。

已完成:
- M0: 项目基础设施
- M1: 最小可跑通 Demo
- M2: LLM Provider (DeepSeek / OpenAI / Anthropic + CLI)
- M3.1: Skill 套件 + State 模块 + CLI 骨架扩展
- M3.2: `videoflow-align` MCP (字级字幕对齐)
- M3.3: `videoflow-playwright` MCP (屏幕录制)
- M3.4a: `videoflow-remotion` MCP (动画渲染: TitleCard + Chart)
- M3.4b: `videoflow-remotion` MCP (动画渲染: Diagram + Image + ScreenCapture + StockFootage)
- M4: 审核 UI (Streamlit 多页面应用)
- M5: 渲染器打磨 (Ken Burns / Mermaid CLI / 缓动曲线)
- M6: 模板系统 (4 类内置模板 + 自定义模板支持)

下一站:**M2** — TTS Provider (Azure / ElevenLabs)
