# Videoflow 中文文档

> 文本 → 视频 · AI 驱动的短视频生成流水线

---

## 5 分钟快速开始

```bash
# 1. 创建虚拟环境
python -m venv .venv && source .venv/bin/activate

# 2. 安装依赖
pip install -e ".[dev]"

# 3. 生成视频（AI 智能规划分镜）
python -m videoflow.cli generate examples/stock-myths/input.md --plan --output workspace/demo.mp4

# 4. 查看结果
open workspace/demo.mp4
```

---

## 核心命令

```bash
# plan: 使用 LLM 生成专业分镜脚本
python -m videoflow.cli plan "公司为什么上市分钱给陌生人？" -o plan.json

# generate: 从 Markdown 或分镜计划生成视频
python -m videoflow.cli generate input.md --output out.mp4              # 从 Markdown
python -m videoflow.cli generate input.md --plan --output out.mp4      # 带 AI 规划
python -m videoflow.cli generate plan.json --output out.mp4            # 从分镜计划

# parse: 解析 Markdown 为分镜结构
python -m videoflow.cli parse input.md --output shots.json

# 其他命令
python -m videoflow.cli list                    # 列出项目
python -m videoflow.cli doctor                  # 系统诊断
```

---

## 功能特性

| 功能 | 状态 | 说明 |
|------|------|------|
| AI 分镜规划 | ✅ | LLM 生成专业短视频分镜脚本 |
| 图表渲染 | ✅ | 柱状图、饼图、折线图、散点图 |
| 流程图渲染 | ✅ | Mermaid DSL 流程图 |
| 图片渲染 | ✅ | 本地/网络图片 |
| 语音合成 | ✅ | 免费 edge-tts，多种音色 |
| 交互模式 | ✅ | 生成前选择视觉类型、语音 |
| 字幕生成 | ✅ | ASS 格式 |
| 视频合成 | ✅ | FFmpeg 拼接 |

---

## AI 分镜规划

使用 AI 生成专业视频脚本：

```bash
# 指定主题文本
python -m videoflow.cli plan "公司为什么上市分钱给陌生人？" --duration 60

# 从 Markdown 文件读取
python -m videoflow.cli plan examples/stock-myths/input.md

# 保存分镜计划
python -m videoflow.cli plan "你的主题" -o myplan.json

# 使用分镜计划生成视频
python -m videoflow.cli generate myplan.json --output out.mp4
```

生成计划后，会提示：
- **Y**: 继续生成视频
- **n**: 取消并保存计划

使用 `--no-interactive` 跳过确认提示。

输出示例：
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

### 分镜视觉类型

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| `title_card` | 标题卡片 | 开场悬念、结尾总结 |
| `chart` | 图表 | 数据对比、趋势展示 |
| `diagram` | 流程图 | 流程说明、关系展示 |
| `image` | 图片 | 真实照片 |

---

## 交互模式

默认情况下，CLI 会显示预览并允许自定义：

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

### 可用 TTS 语音

| 语音 | 说明 |
|------|------|
| `zh-CN-YunxiNeural` | 🌟 男声, 活泼阳光 (默认) |
| `zh-CN-XiaoxiaoNeural` | 💫 女声, 温暖自然 |
| `zh-CN-YunyangNeural` | 📺 男声, 专业播音 |
| `zh-CN-YunjianNeural` | ⚽ 男声, 激情澎湃 |
| `zh-CN-XiaoyiNeural` | 🎬 女声, 活泼可爱 |
| `en-US-AriaNeural` | 🇺🇸 英文女声 |

### 跳过交互模式

```bash
# 非交互模式（用于脚本/CI）
python -m videoflow.cli generate input.md --plan --no-interactive --output out.mp4
```

---

## 输入格式

### Markdown 视觉块

```markdown
# 视频标题

## 章节1

内容...

:::chart bar
title: 数据对比
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

### 支持的视觉块

| 块 | 语法 |
|------|------|
| 柱状图 | `:::chart bar` 配合 `data:` |
| 折线图 | `:::chart line` |
| 饼图 | `:::chart pie` |
| 流程图 | ` ```mermaid` 代码块 |
| 图片 | `:::image path: ...` |

---

## 配置

### 环境变量

在 `.env` 中设置 API key：

```bash
DEEPSEEK_API_KEY=sk-xxx      # LLM 规划 (推荐)
OPENAI_API_KEY=sk-xxx        # 备选 LLM
```

### 配置文件

编辑 `config.toml`：

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

## 常见问题

**找不到 `videoflow` 模块**
```bash
source .venv/bin/activate
pip install -e .
```

**缺少中文字体**
```bash
# macOS
brew install font-noto-sans-cjk
# Ubuntu
sudo apt install fonts-noto-cjk
```

**字幕未烧入视频**
Homebrew FFmpeg 默认不含 libass。ASS 文件仍会生成，可手动合并。

---

## 相关文档

- [English README](./README.md)
- [产品需求文档](./docs/PRD_zh.md)
- [开发路线图](./TODO_LIST.md)

---

## License

[MIT](./LICENSE)
