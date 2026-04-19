"""Tests for :func:`videoflow.state.stage_timings` / ``event_summary`` (M7.3)."""

from __future__ import annotations

from pathlib import Path

from videoflow import state


def _seed(db_path: Path, project_id: str = "proj_timings01") -> None:
    """Create a tiny DB with one fully-done stage and one mid-flight stage."""
    state.init_db(db_path)
    state.upsert_project(
        db_path,
        project_id=project_id,
        workspace_dir=db_path.parent,
        status="created",
    )


class TestStageTimings:
    def test_all_stages_reported_in_order(self, tmp_path: Path):
        db = tmp_path / "videoflow.db"
        _seed(db)

        timings = state.stage_timings(db, "proj_timings01")
        assert [t.stage for t in timings] == list(state.STAGES_ORDERED)
        # Fresh project: every stage is pending.
        assert all(t.status == "pending" for t in timings)
        assert all(t.duration_s is None for t in timings)

    def test_done_stage_has_duration(self, tmp_path: Path):
        db = tmp_path / "videoflow.db"
        _seed(db)

        state.record_event(db, project_id="proj_timings01", stage=state.STAGE_PARSE,
                           status=state.STATUS_STARTED)
        state.record_event(db, project_id="proj_timings01", stage=state.STAGE_PARSE,
                           status=state.STATUS_DONE)

        timings = state.stage_timings(db, "proj_timings01")
        parse = next(t for t in timings if t.stage == state.STAGE_PARSE)
        assert parse.status == "done"
        assert parse.duration_s is not None
        assert parse.duration_s >= 0

    def test_started_without_done_is_running(self, tmp_path: Path):
        db = tmp_path / "videoflow.db"
        _seed(db)
        state.record_event(
            db, project_id="proj_timings01", stage=state.STAGE_TTS,
            status=state.STATUS_STARTED,
        )

        timings = state.stage_timings(db, "proj_timings01")
        tts = next(t for t in timings if t.stage == state.STAGE_TTS)
        assert tts.status == "running"
        assert tts.duration_s is None

    def test_failed_wins_over_done(self, tmp_path: Path):
        """If a stage logged both, ``failed`` is the authoritative status."""
        db = tmp_path / "videoflow.db"
        _seed(db)
        pid = "proj_timings01"
        state.record_event(db, project_id=pid, stage=state.STAGE_TTS,
                           status=state.STATUS_STARTED)
        state.record_event(db, project_id=pid, stage=state.STAGE_TTS,
                           status=state.STATUS_DONE)
        state.record_event(db, project_id=pid, stage=state.STAGE_TTS,
                           status=state.STATUS_FAILED,
                           payload={"error": "network"})

        timings = state.stage_timings(db, pid)
        tts = next(t for t in timings if t.stage == state.STAGE_TTS)
        assert tts.status == "failed"


class TestEventSummary:
    def test_empty_project_returns_zeroed_summary(self, tmp_path: Path):
        db = tmp_path / "videoflow.db"
        _seed(db)
        summary = state.event_summary(db, "proj_timings01")
        assert summary["total_events"] == 0
        assert summary["failures"] == 0
        assert summary["wall_time_s"] is None

    def test_counts_failures(self, tmp_path: Path):
        db = tmp_path / "videoflow.db"
        _seed(db)
        pid = "proj_timings01"
        state.record_event(db, project_id=pid, stage=state.STAGE_PARSE,
                           status=state.STATUS_STARTED)
        state.record_event(db, project_id=pid, stage=state.STAGE_PARSE,
                           status=state.STATUS_DONE)
        state.record_event(db, project_id=pid, stage="pipeline",
                           status=state.STATUS_FAILED,
                           payload={"error": "oom"})

        summary = state.event_summary(db, pid)
        assert summary["total_events"] == 3
        assert summary["failures"] == 1
        assert summary["first_ts"] is not None
        assert summary["last_ts"] is not None
        assert summary["wall_time_s"] is not None
        assert len(summary["stages"]) == len(state.STAGES_ORDERED)
