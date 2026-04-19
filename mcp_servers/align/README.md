# videoflow-align

MCP Server providing **word-level subtitle alignment** via
[`faster-whisper`](https://github.com/SYSTRAN/faster-whisper) (default
model: `base`, ~150 MB, multilingual, CPU-friendly).

## Why a separate MCP server?

See the orchestration decision table at the top of
[`../../TODO_LIST.md`](../../TODO_LIST.md):

> **MCP Server** is used only when we hit one of:
>   ① a long-running model needs to stay warm (cold-start >3s or >200MB RAM)
>   ② cross-language runtime (Node / Browser)
>   ③ must be reusable from non-Claude clients

`faster-whisper base` costs ~600 MB RAM and 2–4 s cold start, so keeping it
warm in a dedicated MCP process is worth it.

## Install

```bash
# From repo root
pip install -e ./mcp_servers/align[dev]
# First run downloads the faster-whisper base model (~150 MB) into
# ``$HOME/.cache/huggingface/``.
```

## Run (standalone)

```bash
videoflow-align                       # stdio transport (default)
videoflow-align --transport sse       # server-sent events on localhost:8765
```

## Tools exposed

### `align_subtitle`

| Argument       | Type      | Default   | Description                                                    |
|----------------|-----------|-----------|----------------------------------------------------------------|
| `audio_path`   | string    | —         | Absolute path to MP3 / WAV.                                    |
| `text`         | string    | —         | Expected transcript; used as initial prompt + for fallback.    |
| `output_ass`   | string    | —         | Where to write the ASS file.                                   |
| `language`     | string    | `"auto"`  | ISO code (e.g. `zh`, `en`) or `"auto"` for detection.          |
| `model_size`   | string    | `"base"`  | Any faster-whisper size: `tiny` / `base` / `small` / …        |
| `word_timestamps` | bool   | `true`    | Emit one ASS event per word with ``{\k}`` karaoke tags.        |

Returns:

```json
{
    "output_path": "/path/to/final.ass",
    "duration": 42.17,
    "num_segments": 12,
    "num_words": 187,
    "language_detected": "zh"
}
```

## Claude Code MCP config

Add to `.claude/mcp.json`:

```json
{
  "mcpServers": {
    "videoflow-align": {
      "command": "videoflow-align",
      "args": []
    }
  }
}
```

## Tests

```bash
# Unit tests (fast, mock faster-whisper)
pytest mcp_servers/align/tests/ -v

# Integration test — spawns the server over stdio and runs a real
# transcription. Requires faster-whisper install + first-run model download.
pytest mcp_servers/align/tests/ -v -m mcp_integration
```
