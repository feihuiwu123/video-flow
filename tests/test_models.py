"""Unit tests for videoflow.models."""

import pytest
from pydantic import ValidationError

from videoflow.models import (
    Project,
    ProjectStatus,
    Renderer,
    Shot,
    ShotList,
    TitleCardVisual,
)


def _make_shot(**overrides) -> Shot:
    defaults = dict(
        shot_id="S01",
        start=0.0,
        end=5.0,
        narration="hello",
        visual=TitleCardVisual(text="Hello"),
        renderer=Renderer.STATIC,
    )
    defaults.update(overrides)
    return Shot(**defaults)


class TestShot:
    def test_valid_shot_duration(self):
        shot = _make_shot(start=1.0, end=4.5)
        assert shot.duration == pytest.approx(3.5)

    def test_end_before_start_rejected(self):
        with pytest.raises(ValidationError):
            _make_shot(start=5.0, end=3.0)

    def test_equal_start_end_rejected(self):
        with pytest.raises(ValidationError):
            _make_shot(start=2.0, end=2.0)

    def test_shot_id_pattern_enforced(self):
        with pytest.raises(ValidationError):
            _make_shot(shot_id="shot_1")

    def test_empty_narration_rejected(self):
        with pytest.raises(ValidationError):
            _make_shot(narration="")


class TestShotList:
    def test_accepts_valid_list(self):
        shots = [_make_shot(shot_id="S01"), _make_shot(shot_id="S02", start=5, end=10)]
        sl = ShotList(shots=shots)
        assert len(sl.shots) == 2
        assert sl.version == "1"

    def test_duplicate_ids_rejected(self):
        with pytest.raises(ValidationError):
            ShotList(shots=[_make_shot(shot_id="S01"), _make_shot(shot_id="S01", start=5, end=10)])

    def test_empty_list_rejected(self):
        with pytest.raises(ValidationError):
            ShotList(shots=[])

    def test_retime_from_audio_updates_timings(self):
        shots = [_make_shot(shot_id="S01"), _make_shot(shot_id="S02", start=5, end=10)]
        sl = ShotList(shots=shots)
        sl.retime_from_audio({"S01": 3.0, "S02": 4.0})
        assert sl.shots[0].start == 0.0
        assert sl.shots[0].end == 3.0
        assert sl.shots[1].start == 3.0
        assert sl.shots[1].end == 7.0
        assert sl.actual_duration == 7.0

    def test_retime_missing_shot_raises(self):
        shots = [_make_shot(shot_id="S01")]
        sl = ShotList(shots=shots)
        with pytest.raises(KeyError):
            sl.retime_from_audio({})


class TestProject:
    def test_new_project_creates_workspace(self, tmp_path):
        project = Project.new(tmp_path)
        assert project.workspace_dir.exists()
        assert (project.workspace_dir / "audio").is_dir()
        assert (project.workspace_dir / "scenes").is_dir()
        assert (project.workspace_dir / "subtitles").is_dir()
        assert project.status == ProjectStatus.CREATED
        assert project.project_id.startswith("proj_")
