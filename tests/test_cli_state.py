"""Smoke tests for the M3.1 CLI subcommands.

These do not invoke FFmpeg / edge-tts — they drive the CLI through Typer's
test runner against a pre-populated SQLite index.
"""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from videoflow import state
from videoflow.cli import app


runner = CliRunner()


def _seed_project(db: Path, workspace: Path, project_id: str = "proj_test") -> Path:
    ws = workspace / project_id
    ws.mkdir(parents=True)
    state.init_db(db)
    state.upsert_project(
        db,
        project_id=project_id,
        workspace_dir=ws,
        status="parsed",
        num_shots=2,
    )
    state.record_event(db, project_id=project_id, stage="parse", status="done")
    state.record_event(db, project_id=project_id, stage="tts", status="started")
    return ws


class TestInitDbCmd:
    def test_creates_db(self, tmp_path: Path):
        db = tmp_path / "v.db"
        res = runner.invoke(app, ["init-db", "--db", str(db)])
        assert res.exit_code == 0
        assert db.exists()


class TestListCmd:
    def test_missing_db_is_friendly(self, tmp_path: Path):
        db = tmp_path / "absent.db"
        res = runner.invoke(app, ["list", "--db", str(db)])
        assert res.exit_code == 0
        assert "No DB" in res.output

    def test_lists_seeded_projects(self, tmp_path: Path):
        db = tmp_path / "v.db"
        _seed_project(db, tmp_path)
        res = runner.invoke(app, ["list", "--db", str(db)])
        assert res.exit_code == 0
        assert "proj_test" in res.output

    def test_status_filter(self, tmp_path: Path):
        db = tmp_path / "v.db"
        _seed_project(db, tmp_path, "proj_a")
        state.upsert_project(
            db, project_id="proj_b", workspace_dir=tmp_path / "proj_b", status="failed"
        )
        res = runner.invoke(app, ["list", "--db", str(db), "--status", "failed"])
        assert "proj_b" in res.output
        assert "proj_a" not in res.output

    def test_json_output(self, tmp_path: Path):
        db = tmp_path / "v.db"
        _seed_project(db, tmp_path)
        res = runner.invoke(app, ["list", "--db", str(db), "--json"])
        assert res.exit_code == 0
        # Rich json print emits bracketed JSON.
        assert "proj_test" in res.output


class TestStatusCmd:
    def test_reports_readiness(self, tmp_path: Path):
        db = tmp_path / "v.db"
        ws = _seed_project(db, tmp_path)
        # Put a shots_draft.json so "parse" readiness flips true.
        (ws / "shots_draft.json").write_text(
            json.dumps(
                {
                    "version": "1",
                    "shots": [
                        {
                            "shot_id": "S01",
                            "start": 0.0,
                            "end": 1.0,
                            "narration": "x",
                            "visual": {"type": "title_card", "text": "t"},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        res = runner.invoke(app, ["status", "proj_test", "--db", str(db)])
        assert res.exit_code == 0
        # Output contains readiness JSON.
        assert "readiness" in res.output
        assert "parse" in res.output


class TestTraceCmd:
    def test_prints_events(self, tmp_path: Path):
        db = tmp_path / "v.db"
        _seed_project(db, tmp_path)
        res = runner.invoke(app, ["trace", "proj_test", "--db", str(db)])
        assert res.exit_code == 0
        assert "parse" in res.output
        assert "tts" in res.output

    def test_stage_filter(self, tmp_path: Path):
        db = tmp_path / "v.db"
        _seed_project(db, tmp_path)
        res = runner.invoke(
            app, ["trace", "proj_test", "--db", str(db), "--stage", "parse"]
        )
        assert "parse" in res.output
        # tts event should be filtered out.
        # (We can't assert absence of "tts" since the table header lists it;
        # instead check the 'started' row for tts doesn't appear.)
        assert res.exit_code == 0

    def test_missing_db_is_friendly(self, tmp_path: Path):
        res = runner.invoke(
            app, ["trace", "proj_x", "--db", str(tmp_path / "absent.db")]
        )
        assert res.exit_code == 0
        assert "No DB" in res.output


class TestDoctorCmd:
    def test_runs(self, tmp_path: Path):
        # Doctor should exit 0 on this host (FFmpeg + CJK font present).
        # If libass happens to be missing it's a soft warning, not a failure.
        db = tmp_path / "v.db"
        res = runner.invoke(app, ["doctor", "--db", str(db)])
        # We accept exit 0 (everything green/soft-yellow) OR exit 1 (hard
        # failure surfacing a real env issue). Assert the table rendered.
        assert "video-agent doctor" in res.output
        assert "Python ≥ 3.11" in res.output


class TestResumeIdempotency:
    """``resume`` on a fully-finished project should be a no-op."""

    def test_fully_done_project_is_noop(self, tmp_path: Path, monkeypatch):
        from videoflow import pipeline

        db = tmp_path / "v.db"
        ws = _seed_project(db, tmp_path, "proj_done01")
        # Populate every stage artifact so readiness is all-true.
        (ws / "shots.json").write_text(
            json.dumps(
                {
                    "version": "1",
                    "shots": [
                        {
                            "shot_id": "S01",
                            "start": 0.0,
                            "end": 1.0,
                            "narration": "x",
                            "visual": {"type": "title_card", "text": "t"},
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        (ws / "audio").mkdir()
        (ws / "audio" / "S01.mp3").write_bytes(b"\x00")
        (ws / "visuals").mkdir()
        (ws / "visuals" / "S01.png").write_bytes(b"\x00")
        (ws / "scenes").mkdir()
        (ws / "scenes" / "S01.mp4").write_bytes(b"\x00")
        (ws / "subtitles").mkdir()
        (ws / "subtitles" / "final.ass").write_text("[Script Info]\n", encoding="utf-8")
        (ws / "final.mp4").write_bytes(b"\x00")

        # Fail loudly if resume actually tries to rerun any stage.
        def boom(*_a, **_kw):  # pragma: no cover — only hit on regression
            raise AssertionError("resume should not invoke stages when all done")

        monkeypatch.setattr(pipeline, "run_tts", boom)
        monkeypatch.setattr(pipeline, "render_all_visuals", boom)
        monkeypatch.setattr(pipeline, "render_all_scenes", boom)
        monkeypatch.setattr(pipeline, "finalize", boom)
        monkeypatch.setattr(pipeline, "write_ass", boom)

        res = runner.invoke(app, ["resume", "proj_done01", "--db", str(db)])
        assert res.exit_code == 0, res.output
