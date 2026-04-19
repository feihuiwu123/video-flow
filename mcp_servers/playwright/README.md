# videoflow-playwright

MCP Server for **screen capture to video** using Playwright + ffmpeg.
Records browser sessions as MP4 files with configurable viewport, duration,
and interaction scripts.

## Why a separate MCP server?

See the orchestration decision table at the top of
[`../../TODO_LIST.md`](../../TODO_LIST.md):

> **MCP Server** is used only when we hit one of:
>   ① a long-running model needs to stay warm (cold-start >3s or >200MB RAM)
>   ② cross-language runtime (Node / Browser)
>   ③ must be reusable from non-Claude clients

Playwright's Chromium instance is ~150MB and takes 2–4s to cold-start.
Keeping a warm instance in this dedicated MCP process makes subsequent
recordings near-instant.

## Prerequisites

```bash
# Install Playwright MCP
pip install -e ./mcp_servers/playwright[dev]

# Install Chromium browser (required!)
playwright install chromium
```

## Install

```bash
# From repo root
pip install -e ./mcp_servers/playwright[dev]

# Or for just the runtime dependency
pip install -e ./mcp_servers/playwright
```

## Run (standalone)

```bash
# Default: headless Chromium, stdio transport
videoflow-playwright

# Show browser window
videoflow-playwright --headless false

# Use installed Chrome channel
videoflow-playwright --browser-channel chrome
```

## Tools exposed

### `capture_url`

Record a URL as an MP4 video.

| Argument          | Type    | Default | Description                              |
|-------------------|---------|---------|------------------------------------------|
| `url`             | string  | —       | URL to capture.                          |
| `output_path`     | string  | —       | Output MP4 file path.                    |
| `duration`        | number  | 5       | Recording duration in seconds.          |
| `viewport_width`   | integer | 1920    | Browser viewport width.                  |
| `viewport_height`  | integer | 1080    | Browser viewport height.                 |
| `fps`             | integer | 30      | Frame rate.                              |
| `quality`         | string  | "high"  | Video quality: low, medium, high.        |

**Returns:**

```json
{
  "output_path": "/path/to/output.mp4",
  "duration": 5.2,
  "width": 1920,
  "height": 1080,
  "fps": 30,
  "file_size": "2.1 MB"
}
```

### `capture_url_with_interactions`

Record a URL with interaction scripts (clicks, scrolls, typing).

| Argument            | Type     | Description                                     |
|--------------------|----------|------------------------------------------------|
| `url`              | string   | URL to capture.                                |
| `output_path`      | string   | Output MP4 file path.                           |
| `duration`         | number   | Recording duration in seconds.                  |
| `clicks`           | array    | `[{selector: CSS selector}, ...]`               |
| `scrolls`          | array    | `[{selector: CSS selector, x: number, y: number}, ...]` |
| `type_texts`       | array    | `[{selector: CSS selector, text: string}, ...]` |
| `wait_for_selectors` | array | `["selector", ...]` — wait before recording    |

### `check_browser`

Check if Playwright and Chromium are available.

```json
{
  "playwright": "✓ 1.40.0",
  "ffmpeg": "✓ /usr/bin/ffmpeg",
  "chromium": "✓ available"
}
```

## Claude Code MCP config

Add to `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "videoflow-playwright": {
      "command": "videoflow-playwright",
      "args": ["--headless", "true"]
    }
  }
}
```

## Usage examples

### Basic capture

```python
import asyncio
from pathlib import Path
from videoflow_playwright import record_screen

async def main():
    result = await record_screen(
        url="https://example.com",
        output_path=Path("output.mp4"),
        duration=5.0,
    )
    print(f"Recorded: {result.duration}s, {result.file_size}")

asyncio.run(main())
```

### With interactions

```python
from videoflow_playwright import BrowserRecorder, RecordingOptions, Viewport

async def main():
    recorder = await BrowserRecorder.get_instance()

    options = RecordingOptions(
        url="https://github.com/login",
        output_path=Path("github_login.mp4"),
        duration=10.0,
        viewport=Viewport(width=1280, height=720),
        wait_for_selectors=["#login-form"],
        type_texts=[
            {"selector": "#login_field", "text": "user@example.com"},
            {"selector": "#password", "text": "secret123"},
        ],
        clicks=[{"selector": "button[type=submit]"}],
    )

    result = await recorder.record(options)
    print(f"Recorded: {result.output_path}")

asyncio.run(main())
```

## Tests

```bash
# Unit tests (fast, no browser required)
pytest mcp_servers/playwright/tests/ -v --ignore=tests/integration

# Integration tests (requires playwright + chromium)
playwright install chromium
pytest mcp_servers/playwright/tests/ -v -m pw_integration
```
