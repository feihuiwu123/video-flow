---
name: videoflow
description: |
  Text-to-video pipeline. Turns a Markdown script into a 1080×1920 MP4 via
  parse → edge-tts → Pillow title cards → FFmpeg. Exposes three sub-skills:
  generate (end-to-end auto mode), review (light-mode human approval),
  resume (idempotent continuation).
version: 0.1.0
trigger_examples:
  - "把 input.md 转成竖屏视频"
  - "review the shots for proj_xxx"
  - "resume proj_xxx"
tools:
  - Bash
  - Read
  - Edit
  - Write
---

# Videoflow Skill

Entry point for the `videoflow` text-to-video pipeline. Use this when the
user asks to convert a Markdown script into a short video, review a
parsed shot list, or pick up a paused pipeline run.

## Preflight (always run first)

```bash
video-agent doctor
```

Fix any red `✗` before continuing. Yellow `·` entries for MCPs (align /
playwright / remotion) are informational — they are implemented in M3.2+
and not required for the basic title-card pipeline.

## Sub-skills

| Sub-skill      | When to use                                                    | File              |
|----------------|----------------------------------------------------------------|-------------------|
| `generate.md`  | User provides a Markdown file and wants a finished MP4         | `./generate.md`   |
| `review.md`    | User wants to approve / edit shots before TTS runs             | `./review.md`     |
| `resume.md`    | Pipeline crashed, user edited `shots.json`, or staged re-run   | `./resume.md`     |

## Shared conventions

- **Project IDs** look like `proj_YYMMDDhhmmss`. CLI commands resolve them
  via the SQLite index at `<workspace_root>/videoflow.db`.
- **Filesystem is truth**: artifacts live at
  `workspace/<project_id>/{shots_draft.json, shots.json, audio/, visuals/,
  scenes/, subtitles/final.ass, final.mp4}`.
- **`video-agent status <id>`** returns JSON with per-stage readiness —
  always run it before deciding what to do next.
- **Never hand-edit scene MP4s.** If shots change, delete the
  `scenes/<shot_id>.mp4` + `visuals/<shot_id>.png` for affected shots and
  run `video-agent resume <id>`.

## Quick dispatcher

- User says "生成 / generate / render": load `./generate.md`.
- User says "review / 审核 / 确认": load `./review.md`.
- User says "resume / 继续 / 续跑": load `./resume.md`.
