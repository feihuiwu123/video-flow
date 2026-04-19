---
name: videoflow-review
description: Light-mode human review between parsing and TTS. One confirmation.
parent: videoflow
---

# Review (light mode)

Goal: insert exactly **one** human checkpoint between "shots parsed" and
"TTS synthesised". The user approves / edits `shots.json`, then the rest
of the pipeline runs unattended.

## Procedure

1. **Parse only** — do not call `generate` (it runs end-to-end without
   stopping):
   ```bash
   video-agent parse <input.md> --output workspace/tmp_shots.json
   ```
   This writes a draft ShotList (estimated timings, audio/visual paths
   empty).

2. **Present the parsed shots to the user**. For each shot, show:
   - `shot_id` (e.g. `S01`)
   - `narration` (first 80 chars)
   - `visual.text` (title card headline)
   - estimated `duration`

3. **Capture the user's decision per shot**:
   - `approve` → no change
   - `edit` → let the user rewrite narration / headline / duration; apply
     the edits to the JSON in place
   - `reject` → remove the shot from the list

4. **Log review actions to the DB** (so the audit UI in M4 can replay
   them). Use a short Python helper:
   ```python
   from pathlib import Path
   from videoflow import state
   from videoflow.config import load_config

   cfg = load_config(Path("config.toml"))
   db = state.default_db_path(cfg.runtime.workspace_root)
   state.init_db(db)
   state.record_review(db, project_id="<pid>", shot_id="S01", decision="approved")
   state.record_review(db, project_id="<pid>", shot_id="S02", decision="edited", note="tightened wording")
   ```

5. **Stage the approved JSON into a fresh project workspace**:
   ```bash
   # Create the workspace by running generate in dry mode… actually the
   # minimal-friction route today is: feed the edited ShotList straight
   # to a new project dir.
   PROJECT_ID="proj_$(date -u +%y%m%d%H%M%S)"
   mkdir -p "workspace/${PROJECT_ID}/audio" "workspace/${PROJECT_ID}/visuals" \
            "workspace/${PROJECT_ID}/scenes" "workspace/${PROJECT_ID}/subtitles"
   cp workspace/tmp_shots.json "workspace/${PROJECT_ID}/shots_draft.json"
   ```

6. **Register the project in the DB** and resume from stage 2 onwards:
   ```python
   state.upsert_project(
       db,
       project_id=PROJECT_ID,
       workspace_dir=Path(f"workspace/{PROJECT_ID}"),
       status="parsed",
   )
   ```
   ```bash
   video-agent resume ${PROJECT_ID} --output workspace/${PROJECT_ID}/final.mp4
   ```

7. **Report back**: project_id, output path, number of approved / edited /
   rejected shots.

## Guarantees

- Exactly **one** human checkpoint (step 3). Do not ask the user again
  between TTS and render — that is full-mode review (out of scope).
- Every decision is persisted to `reviews` (step 4). If the user wants to
  undo, they can delete the workspace and rerun.

## Do NOT

- Do not skip the DB insert — downstream UIs and `video-agent list`
  depend on it.
- Do not modify `shot_id` values; they are the contract between audio
  files, visual PNGs, and scene MP4s.
