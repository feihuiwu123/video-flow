---
name: videoflow-resume
description: Idempotent resume — rerun only the stages whose artifacts are missing.
parent: videoflow
---

# Resume

Goal: pick up a project where it left off, running exactly the stages
whose artifacts don't yet exist on disk. Safe to invoke repeatedly.

## Procedure

1. **Identify the project**:
   ```bash
   video-agent list --limit 10
   ```
   Pick the `project_id` (`proj_YYMMDDhhmmss`). If the user points at a
   workspace dir instead of an ID, use the directory name as the ID.

2. **Inspect stage readiness** (filesystem is truth):
   ```bash
   video-agent status <project_id>
   ```
   The JSON response includes `readiness` (one boolean per stage) and
   `next_stage` (first missing one, or `null` if done).

3. **Run resume**:
   ```bash
   video-agent resume <project_id>
   ```
   Each stage with `readiness[stage] == false` executes; the rest are
   skipped silently. Events are appended to `events` with
   `{"resume": true}` in the payload so `trace` can distinguish them from
   a fresh run.

4. **If resume fails**, inspect the event log:
   ```bash
   video-agent trace <project_id> --tail 20
   ```
   Look for the last `status=failed` row; its `payload.error` names the
   failure. Fix the root cause, then rerun step 3.

## When the user has hand-edited `shots.json`

If the user changed narration / timing for some shots, the affected
scenes must be rebuilt. Because resume trusts existing files:

```bash
# Delete the affected stage artifacts so resume picks them up.
rm workspace/<project_id>/audio/S03.mp3
rm workspace/<project_id>/visuals/S03.png
rm workspace/<project_id>/scenes/S03.mp4
# Also clear the final MP4 + concat raw so finalize reruns.
rm -f workspace/<project_id>/final.mp4 workspace/<project_id>/_concat_raw.mp4
rm -f workspace/<project_id>/subtitles/final.ass
video-agent resume <project_id>
```

## Guarantees

- **Idempotent**: running `resume` on an already-complete project is a no-op.
- **Atomic per stage**: a crashed stage leaves partial artifacts; resume
  re-reads the filesystem and redoes the stage from scratch.
- **DB is best-effort**: if `videoflow.db` is missing, `resume` still
  works (events are silently dropped).

## Do NOT

- Do not delete `shots_draft.json` or `shots.json` unless you intend to
  re-parse from the original Markdown. Without a shot list, resume has
  nothing to iterate over.
- Do not mix `video-agent generate` and `resume` on the same project —
  `generate` always creates a *new* `proj_xxx`.
