"""Integration test — real FFmpeg, real edge-tts network call.

Guarded by ``--run-integration`` (see conftest.py). Skipped by default.
"""

from pathlib import Path

import pytest


@pytest.mark.integration
def test_end_to_end(tmp_path):
    """Runs the full pipeline against the shipped sample."""
    from videoflow.config import Config
    from videoflow.pipeline import run_pipeline

    input_path = Path(__file__).parent.parent / "examples" / "stock-myths" / "input.md"
    assert input_path.exists(), "sample input missing"

    output = tmp_path / "final.mp4"
    cfg = Config()
    cfg.runtime.workspace_root = tmp_path / "workspace"

    project = run_pipeline(input_path, output, config=cfg, workspace_root=cfg.runtime.workspace_root)

    # Output must exist and be non-trivial.
    assert output.exists()
    assert output.stat().st_size > 10_000

    # Internal artifacts present.
    assert (project.workspace_dir / "shots.json").exists()
    assert (project.workspace_dir / "subtitles" / "final.ass").exists()
    for shot in project.shotlist.shots:
        assert shot.audio_file and shot.audio_file.exists()
        assert shot.visual_file and shot.visual_file.exists()
        # Visual PNG should be the full target resolution.
        from PIL import Image

        with Image.open(shot.visual_file) as im:
            assert im.size == (1080, 1920)

    # Duration sanity: sum of shot durations ~= project.shotlist.actual_duration.
    assert project.shotlist.actual_duration and project.shotlist.actual_duration > 5.0
