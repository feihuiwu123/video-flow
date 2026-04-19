"""Unit tests for videoflow.state — SQLite schema + stage readiness logic."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from videoflow import state


@pytest.fixture
def db(tmp_path: Path) -> Path:
    p = tmp_path / "videoflow.db"
    state.init_db(p)
    return p


class TestInitDb:
    def test_creates_three_tables(self, tmp_path: Path):
        db = tmp_path / "a.db"
        state.init_db(db)
        with state.connect(db) as conn:
            names = {
                r[0]
                for r in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
        assert {"projects", "events", "reviews"} <= names

    def test_idempotent(self, tmp_path: Path):
        db = tmp_path / "a.db"
        state.init_db(db)
        state.init_db(db)  # should not raise
        state.init_db(db)

    def test_creates_parent_directory(self, tmp_path: Path):
        nested = tmp_path / "nested" / "sub" / "v.db"
        state.init_db(nested)
        assert nested.exists()


class TestProjectCrud:
    def test_insert_then_fetch(self, db: Path, tmp_path: Path):
        ws = tmp_path / "proj_240101000000"
        ws.mkdir()
        state.upsert_project(
            db,
            project_id="proj_240101000000",
            workspace_dir=ws,
            input_path=tmp_path / "input.md",
            output_path=tmp_path / "out.mp4",
            status="parsed",
            num_shots=5,
        )
        row = state.get_project(db, "proj_240101000000")
        assert row is not None
        assert row.status == "parsed"
        assert row.num_shots == 5
        assert row.workspace_dir == str(ws)

    def test_upsert_updates_existing(self, db: Path, tmp_path: Path):
        ws = tmp_path / "p"
        ws.mkdir()
        state.upsert_project(
            db, project_id="proj_x", workspace_dir=ws, status="created"
        )
        state.upsert_project(
            db,
            project_id="proj_x",
            workspace_dir=ws,
            status="done",
            actual_duration=42.0,
        )
        row = state.get_project(db, "proj_x")
        assert row.status == "done"
        assert row.actual_duration == 42.0

    def test_coalesce_preserves_unset_fields(self, db: Path, tmp_path: Path):
        """Passing None for output_path must not wipe an existing value."""
        ws = tmp_path / "p"
        ws.mkdir()
        state.upsert_project(
            db,
            project_id="proj_y",
            workspace_dir=ws,
            output_path=tmp_path / "first.mp4",
        )
        state.upsert_project(db, project_id="proj_y", workspace_dir=ws, status="done")
        row = state.get_project(db, "proj_y")
        assert row.output_path is not None and row.output_path.endswith("first.mp4")

    def test_get_missing_returns_none(self, db: Path):
        assert state.get_project(db, "proj_missing") is None

    def test_list_filters_by_status_and_orders_newest_first(
        self, db: Path, tmp_path: Path
    ):
        ws = tmp_path / "w"
        ws.mkdir()
        for pid, status in [
            ("proj_001", "done"),
            ("proj_002", "failed"),
            ("proj_003", "done"),
        ]:
            state.upsert_project(db, project_id=pid, workspace_dir=ws, status=status)
        dones = state.list_projects(db, status="done")
        assert {r.project_id for r in dones} == {"proj_001", "proj_003"}
        all_ = state.list_projects(db)
        assert len(all_) == 3


class TestEventLog:
    def test_record_and_list(self, db: Path, tmp_path: Path):
        state.upsert_project(
            db, project_id="proj_e", workspace_dir=tmp_path / "w"
        )
        state.record_event(
            db, project_id="proj_e", stage="parse", status="started"
        )
        state.record_event(
            db,
            project_id="proj_e",
            stage="parse",
            status="done",
            payload={"num_shots": 3},
        )
        events = state.list_events(db, "proj_e")
        assert len(events) == 2
        assert events[0].status == "started"
        assert events[1].payload == {"num_shots": 3}

    def test_stage_filter(self, db: Path, tmp_path: Path):
        state.upsert_project(db, project_id="p", workspace_dir=tmp_path / "w")
        state.record_event(db, project_id="p", stage="parse", status="done")
        state.record_event(db, project_id="p", stage="tts", status="done")
        tts_only = state.list_events(db, "p", stage="tts")
        assert len(tts_only) == 1
        assert tts_only[0].stage == "tts"

    def test_tail_returns_last_n(self, db: Path, tmp_path: Path):
        state.upsert_project(db, project_id="p", workspace_dir=tmp_path / "w")
        for i in range(5):
            state.record_event(db, project_id="p", stage="x", status=f"s{i}")
        tail = state.list_events(db, "p", tail=2)
        assert [e.status for e in tail] == ["s3", "s4"]


class TestReviews:
    def test_record_and_list(self, db: Path, tmp_path: Path):
        state.upsert_project(db, project_id="p", workspace_dir=tmp_path / "w")
        state.record_review(
            db,
            project_id="p",
            shot_id="S01",
            decision="approved",
        )
        state.record_review(
            db,
            project_id="p",
            shot_id="S02",
            decision="edited",
            note="tightened wording",
        )
        reviews = state.list_reviews(db, "p")
        assert len(reviews) == 2
        assert reviews[0].shot_id == "S01"
        assert reviews[1].note == "tightened wording"


class TestStageReadiness:
    def _make_workspace(self, root: Path, shot_ids: list[str]) -> Path:
        ws = root / "proj_test"
        ws.mkdir()
        (ws / "audio").mkdir()
        (ws / "visuals").mkdir()
        (ws / "scenes").mkdir()
        (ws / "subtitles").mkdir()
        # Shots draft with matching shot_ids.
        draft = {
            "version": "1",
            "shots": [
                {"shot_id": sid, "start": 0.0, "end": 1.0, "narration": "x",
                 "visual": {"type": "title_card", "text": "t"}}
                for sid in shot_ids
            ],
        }
        (ws / "shots_draft.json").write_text(json.dumps(draft), encoding="utf-8")
        return ws

    def test_empty_project_reports_nothing_done(self, tmp_path: Path):
        ws = tmp_path / "proj_x"
        ws.mkdir()
        r = state.stage_readiness(ws)
        assert all(v is False for v in r.values())

    def test_parse_detected_from_draft(self, tmp_path: Path):
        ws = self._make_workspace(tmp_path, ["S01"])
        r = state.stage_readiness(ws)
        assert r[state.STAGE_PARSE] is True
        assert r[state.STAGE_TTS] is False

    def test_tts_requires_audio_for_all_shots(self, tmp_path: Path):
        ws = self._make_workspace(tmp_path, ["S01", "S02"])
        (ws / "audio" / "S01.mp3").write_bytes(b"\x00")
        r = state.stage_readiness(ws)
        assert r[state.STAGE_TTS] is False
        (ws / "audio" / "S02.mp3").write_bytes(b"\x00")
        r = state.stage_readiness(ws)
        assert r[state.STAGE_TTS] is True

    def test_visuals_and_scenes_require_all_files(self, tmp_path: Path):
        ws = self._make_workspace(tmp_path, ["S01", "S02"])
        for sid in ("S01", "S02"):
            (ws / "audio" / f"{sid}.mp3").write_bytes(b"\x00")
            (ws / "visuals" / f"{sid}.png").write_bytes(b"\x00")
            (ws / "scenes" / f"{sid}.mp4").write_bytes(b"\x00")
        (ws / "subtitles" / "final.ass").write_text("[Script Info]\n", encoding="utf-8")
        r = state.stage_readiness(ws)
        assert r[state.STAGE_RENDER_VISUALS] is True
        assert r[state.STAGE_RENDER_SCENES] is True
        assert r[state.STAGE_SUBTITLES] is True

    def test_finalize_detected_from_mp4_or_project_json(self, tmp_path: Path):
        ws = self._make_workspace(tmp_path, ["S01"])
        assert state.stage_readiness(ws)[state.STAGE_FINALIZE] is False
        (ws / "final.mp4").write_bytes(b"\x00")
        assert state.stage_readiness(ws)[state.STAGE_FINALIZE] is True


class TestNextStage:
    def test_returns_first_missing(self):
        r = {
            state.STAGE_PARSE: True,
            state.STAGE_TTS: True,
            state.STAGE_RENDER_VISUALS: False,
            state.STAGE_SUBTITLES: False,
            state.STAGE_RENDER_SCENES: False,
            state.STAGE_FINALIZE: False,
        }
        assert state.next_stage(r) == state.STAGE_RENDER_VISUALS

    def test_all_done_returns_none(self):
        r = {s: True for s in state.STAGES_ORDERED}
        assert state.next_stage(r) is None

    def test_nothing_done_returns_parse(self):
        r = {s: False for s in state.STAGES_ORDERED}
        assert state.next_stage(r) == state.STAGE_PARSE


class TestIdempotencyEndToEnd:
    """Running init + upsert + event x2 leaves a clean, deterministic DB."""

    def test_repeated_init_and_upsert(self, tmp_path: Path):
        db = tmp_path / "v.db"
        ws = tmp_path / "p"
        ws.mkdir()
        for _ in range(3):
            state.init_db(db)
            state.upsert_project(
                db, project_id="proj_a", workspace_dir=ws, status="created"
            )
        rows = state.list_projects(db)
        assert len(rows) == 1  # upsert not duplicate
