---
name: videoflow-generate
description: End-to-end auto mode — Markdown → MP4 without human checkpoint.
parent: videoflow
---

# Generate (auto mode)

Goal: given an input Markdown file, produce a publishable 1080×1920 MP4
with no manual review step.

## Preconditions

- `video-agent doctor` has passed (FFmpeg on PATH, CJK font discovered,
  workspace writable, DB schema reachable).
- Input file exists and is UTF-8 Markdown.

## Procedure

1. **Confirm DB is initialised** (idempotent; safe to always run):
   ```bash
   video-agent init-db
   ```

2. **Run the pipeline**:
   ```bash
   video-agent generate <input.md> --output workspace/<slug>.mp4
   ```
   Optional flags:
   - `--voice zh-CN-YunxiNeural` (any edge-tts voice)
   - `--config path/to/config.toml`
   - `--no-track` to skip the SQLite event log (useful for throwaway runs)

3. **Verify**:
   ```bash
   video-agent list --limit 5
   video-agent status <project_id>   # expect all readiness flags true
   ```

4. **Report back to the user**:
   - `project_id`
   - `output_path`
   - `num_shots` and `actual_duration`

## Failure modes & recovery

| Symptom                                     | Action                                                |
|---------------------------------------------|-------------------------------------------------------|
| `edge-tts` network error                    | retry; if persistent, swap voice with `--voice`        |
| `ffmpeg failed ... subtitles`               | libass missing — the .ass file is written alongside MP4, user can mux externally |
| `No CJK font found`                         | install `NotoSansCJK` or `PingFang` and re-run doctor  |
| Pipeline crashed mid-way                    | hand off to `./resume.md`                              |

## Do NOT

- Do not call `video-agent tts` / `render` manually when `generate` is
  sufficient — they are stage helpers, not the happy path.
- Do not delete `shots_draft.json`; it is required by `resume` to
  reconstruct the shot list if `shots.json` was removed.
