# videoflow-remotion

MCP Server for **animated video rendering** via [Remotion](https://www.remotion.dev/)
(React + TypeScript). Provides 6 types of animated visuals as MP4 videos:
TitleCards, Charts, Diagrams, Images, ScreenCaptures, and StockFootage.

## Why a separate MCP server?

See the orchestration decision table at the top of
[`../../TODO_LIST.md`](../../TODO_LIST.md):

> **MCP Server** is used only when we hit one of:
>   ① a long-running model needs to stay warm (cold-start >3s or >200MB RAM)
>   ② cross-language runtime (Node / Browser)
>   ③ must be reusable from non-Claude clients

Remotion requires a Node.js runtime with Chromium for rendering. Keeping
this in a dedicated MCP process ensures clean resource management.

## Prerequisites

```bash
# Node.js 18+
node --version  # >= 18.0.0

# Install dependencies
npm install

# Build Remotion bundle (first run only)
npm run bundle
```

## Install

```bash
# From repo root
cd mcp_servers/remotion
npm install
npm run bundle
```

## Run (standalone)

```bash
# Start MCP server over stdio
npm start

# Or with development mode
npm run dev
```

## Tools exposed (6 total)

### `render_title_card`

Render an animated title card with keyword highlighting.

| Argument          | Type    | Description                                |
|-------------------|---------|--------------------------------------------|
| `title`           | string  | Main title text (required)                 |
| `subtitle`        | string  | Subtitle or description                   |
| `keywords`        | array   | Keywords to highlight                     |
| `background_color`| string  | Background color (hex, default: #0A1929)  |
| `text_color`      | string  | Text color (hex, default: #FFFFFF)       |
| `highlight_color` | string  | Keyword highlight (hex, default: #FFD700) |
| `entry_duration`  | number  | Animation duration in seconds (default: 1) |
| `output_path`     | string  | Output file path (auto-generated if none)  |
| `config`          | object  | Remotion overrides (width, height, fps)   |

### `render_chart`

Render an animated chart.

| Argument            | Type    | Description                              |
|---------------------|---------|------------------------------------------|
| `type`              | string  | Chart type: bar, line, pie, scatter      |
| `data`              | array   | Data points: `[{label, value}, ...]`     |
| `title`             | string  | Chart title                              |
| `background_color`  | string  | Background color (hex)                   |
| `chart_color`       | string  | Chart color (hex)                        |
| `show_legend`       | boolean | Show legend (default: true)             |
| `animation_duration`| number  | Animation duration in seconds (default: 2)|
| `output_path`       | string  | Output file path                          |
| `config`           | object  | Remotion overrides                       |

### `render_diagram`

Render a Mermaid diagram with sequential animation.

| Argument            | Type    | Description                              |
|---------------------|---------|------------------------------------------|
| `mermaid_code`      | string  | Mermaid diagram syntax (required)        |
| `background_color`  | string  | Background color (hex)                   |
| `animation`         | string  | Animation: none, fade, sequential        |
| `output_path`       | string  | Output file path                          |
| `config`           | object  | Remotion overrides                       |

### `render_image`

Render an image with Ken Burns pan/zoom effect.

| Argument        | Type    | Description                              |
|-----------------|---------|------------------------------------------|
| `image_url`     | string  | Image URL                                |
| `caption`       | string  | Caption text                             |
| `caption_color` | string  | Caption text color (hex)                 |
| `background_color` | string | Background color                      |
| `direction`    | string  | Ken Burns direction (zoom_in/out, pan_*) |
| `zoom_start`    | number  | Starting zoom (default: 1.0)             |
| `zoom_end`      | number  | Ending zoom (default: 1.15)             |
| `easing`        | string  | Easing function (default: ease_in_out)  |
| `output_path`    | string  | Output file path                          |
| `config`        | object  | Remotion overrides                       |

### `render_screen_capture`

Render a screen capture with annotation overlays.

| Argument          | Type    | Description                              |
|-------------------|---------|------------------------------------------|
| `video_url`       | string  | URL to MP4 from Playwright               |
| `video_path`      | string  | Local MP4 path                           |
| `viewport_width`  | number  | Browser viewport width (default: 1280)   |
| `viewport_height` | number  | Browser viewport height (default: 720)   |
| `annotations`    | array   | Annotation overlays                       |
| `show_pointer`    | boolean | Show pointer animation (default: true)   |
| `background_color` | string | Background color                        |
| `output_path`     | string  | Output file path                          |
| `config`          | object  | Remotion overrides                       |

### `render_stock_footage`

Render stock footage (Pexels) with Ken Burns effect.

| Argument          | Type    | Description                              |
|-------------------|---------|------------------------------------------|
| `video_url`       | string  | Video URL                                |
| `pexels_video_id` | number  | Pexels video ID                         |
| `thumbnail_url`   | string  | Thumbnail/fallback image URL             |
| `direction`       | string  | Ken Burns direction (default: zoom_in) |
| `zoom_start`      | number  | Starting zoom (default: 1.0)             |
| `zoom_end`        | number  | Ending zoom (default: 1.15)             |
| `easing`          | string  | Easing function (default: ease_in_out) |
| `caption`         | string  | Caption text                             |
| `caption_bg_color` | string | Caption background color                 |
| `caption_color`   | string  | Caption text color                       |
| `loop`            | boolean | Loop video (default: true)              |
| `background_color` | string | Background color                        |
| `output_path`    | string  | Output file path                          |
| `config`         | object  | Remotion overrides                       |

### `list_compositions`

List available Remotion compositions.

## Claude Code MCP config

Add to `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "videoflow-remotion": {
      "command": "node",
      "args": ["dist/server.js"],
      "cwd": "/path/to/mcp_servers/remotion"
    }
  }
}
```

## Usage examples

### Render a title card

```typescript
{
  name: "render_title_card",
  arguments: {
    title: "股市反常识",
    subtitle: "你不知道的市场真相",
    keywords: ["股票", "投资", "风险"],
    background_color: "#0A1929",
    highlight_color: "#FFD700",
    output_path: "./out/titlecard.mp4"
  }
}
```

### Render a bar chart

```typescript
{
  name: "render_chart",
  arguments: {
    type: "bar",
    title: "月度销售额",
    data: [
      { label: "1月", value: 120 },
      { label: "2月", value: 150 },
      { label: "3月", value: 180 },
      { label: "4月", value: 160 }
    ],
    chart_color: "#4FC3F7",
    output_path: "./out/chart.mp4"
  }
}
```

### Render a Mermaid diagram

```typescript
{
  name: "render_diagram",
  arguments: {
    mermaid_code: "flowchart TD\nA[Start] --> B[Process]\nB --> C[End]",
    animation: "sequential",
    output_path: "./out/diagram.mp4"
  }
}
```

### Render an image with Ken Burns

```typescript
{
  name: "render_image",
  arguments: {
    image_url: "https://example.com/photo.jpg",
    caption: "Beautiful sunset",
    direction: "zoom_in",
    zoom_start: 1.0,
    zoom_end: 1.2,
    output_path: "./out/image.mp4"
  }
}
```

## Compositions (6 total)

### TitleCard

- Fade-in + scale-up entry animation
- Keyword highlighting with gold color
- Staggered keyword tag reveal
- Supports Chinese fonts (Noto Sans SC)

### Chart

- **Bar**: Vertical bars with animated height growth
- **Line**: Line chart with area fill
- **Pie**: Pie chart with animated slices
- **Scatter**: Scatter plot with animated point reveal

### Diagram

- Mermaid diagram rendering
- Sequential node-by-node animation
- Fade-in animation option
- SVG-based rendering

### Image

- Ken Burns pan/zoom effect
- Supports zoom_in, zoom_out, pan_left, pan_right, pan_up, pan_down
- Caption overlay with styling
- Cinematic vignette overlay

### ScreenCapture

- Browser window frame with header
- Annotation overlays (highlight, arrow, text, circle)
- Pointer animation along path
- Click ripple effect

### StockFootage

- Ken Burns effect on video/image
- Pexels integration (when API key provided)
- Cinematic overlays (vignette, letterbox bars)
- Caption overlay with progress bar
- Attribution display

## Development

```bash
# Type checking
npm run typecheck

# Run tests
npm test

# Build bundle
npm run bundle

# Render test compositions
npm run render:title
npm run render:chart
npm run render:diagram
npm run render:image
```

## Architecture

```
src/
├── server.tsx              # MCP server entry point
├── compositions/
│   ├── TitleCard.tsx       # Title card composition
│   ├── Chart.tsx           # Chart composition
│   ├── Diagram.tsx         # Mermaid diagram composition
│   ├── Image.tsx           # Ken Burns image composition
│   ├── ScreenCapture.tsx    # Screen capture with annotations
│   └── StockFootage.tsx     # Stock footage with Ken Burns
├── lib/
│   └── render.ts           # Rendering utilities
└── types/
    └── index.ts            # Type definitions
```
